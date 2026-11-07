"""Resume parsing: PDF text extraction, LLM profile extraction, safe fallback.

The LLM path is preferred, but a deterministic regex/section-based extractor
runs whenever the LLM is in mock mode, fails, or returns something unusable.
That fallback is what makes the stage demo bulletproof.
"""

from __future__ import annotations

import importlib.util
import io
import logging
import re
import sys
import sysconfig
from pathlib import Path
from types import ModuleType
from typing import Any

from pydantic import BaseModel, Field

import prompts
from llm import LLMClient, get_llm_client
from matching import normalize_skill
from models import Education, Project, StudentProfile

logger = logging.getLogger("scoutly.profile")

DATA_DIR = Path(__file__).resolve().parent / "data"
SAMPLE_RESUME_PATH = DATA_DIR / "sample_resume.txt"

#: Skills the heuristic extractor can recognise in free text.
KNOWN_SKILLS: tuple[str, ...] = (
    "Python", "Java", "C++", "C#", "C", "JavaScript", "TypeScript", "Go", "Rust", "Kotlin",
    "Swift", "Ruby", "PHP", "Scala", "R", "MATLAB", "Bash",
    "React", "Next.js", "Vue", "Angular", "Svelte", "React Native", "Flutter", "Android",
    "Node.js", "Express", "FastAPI", "Django", "Flask", "Spring Boot", "REST API", "GraphQL",
    "HTML", "CSS", "Tailwind CSS", "JavaScript", "Redux",
    "SQL", "PostgreSQL", "MySQL", "MongoDB", "Redis", "SQLite", "Firebase", "Supabase",
    "Docker", "Kubernetes", "AWS", "GCP", "Azure", "Git", "GitHub Actions", "Linux", "CI/CD",
    "Terraform", "Nginx", "Vercel", "Cloudflare",
    "pandas", "NumPy", "scikit-learn", "PyTorch", "TensorFlow", "Keras", "OpenCV",
    "Hugging Face", "LangChain", "LLM", "NLP", "Computer Vision", "Machine Learning",
    "Deep Learning", "Data Structures and Algorithms", "System Design", "Data Engineering",
    "Apache Spark", "Hadoop", "Airflow", "MLOps", "Tableau", "Power BI", "Excel",
    "Figma", "UI/UX Design", "Product Management", "SEO", "Google Analytics",
    "Embedded C", "Arduino", "Raspberry Pi", "IoT", "Verilog", "SolidWorks", "PLC",
    "Cybersecurity", "Penetration Testing", "Jest", "Pytest", "Selenium", "Postman",
    "Agile", "Scrum", "Jira",
)

_KNOWN_NORMALISED: dict[str, str] = {}
for _skill in KNOWN_SKILLS:
    _KNOWN_NORMALISED.setdefault(normalize_skill(_skill), _skill)

SECTION_ALIASES: dict[str, tuple[str, ...]] = {
    "education": ("education", "academic", "academics", "qualification"),
    "skills": ("skills", "technical skills", "tech stack", "technologies", "technical proficiency"),
    "projects": ("projects", "personal projects", "academic projects", "key projects"),
    "experience": ("experience", "work experience", "internship", "internships", "employment"),
    "interests": ("interests", "areas of interest", "interests and hobbies", "hobbies", "strengths & interests", "strengths and interests"),
    "achievements": ("achievements", "awards", "honors", "honours", "accomplishments", "certifications", "certifications & training", "certifications and training"),
}

_HEADING_RE = re.compile(r"^([A-Z][A-Za-z &/]{2,40})\s*:?\s*$")
_BULLET_RE = re.compile(r"^\s*(?:[-*•·]|\d+[.)])\s+")
_SPLIT_SKILLS_RE = re.compile(r"[,;|/•·]|\s{2,}")

INDIAN_CITIES: tuple[str, ...] = (
    "Bengaluru", "Bangalore", "Hyderabad", "Pune", "Chennai", "Mumbai", "Delhi",
    "New Delhi", "Noida", "Gurugram", "Gurgaon", "Ahmedabad", "Kolkata", "Jaipur",
    "Indore", "Coimbatore", "Trichy", "Tiruchirappalli", "Vellore", "Manipal",
    "Chandigarh", "Kochi", "Thiruvananthapuram", "Bhopal", "Nagpur", "Surat",
    "Meerut", "Dehradun", "Remote",
)


class ProfileExtraction(BaseModel):
    """Exactly what the LLM is allowed to return (``raw_text`` is added later)."""

    name: str = ""
    education: Education = Field(default_factory=Education)
    skills: list[str] = Field(default_factory=list)
    projects: list[Project] = Field(default_factory=list)
    experience: list[str] = Field(default_factory=list)
    interests: list[str] = Field(default_factory=list)
    target_types: list[str] = Field(default_factory=list)
    location_pref: str = ""


# ---------------------------------------------------------------------------
# PDF handling
# ---------------------------------------------------------------------------


def extract_text_from_pdf(data: bytes) -> str:
    """Extract plain text from a PDF byte string using pypdf.

    Raises:
        ValueError: if the bytes are not a readable PDF or contain no text
            (e.g. a scanned image resume).
    """
    if not data:
        raise ValueError("The uploaded file was empty.")
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        pages = [(page.extract_text() or "") for page in reader.pages]
    except Exception as exc:
        raise ValueError(
            "That file could not be read as a PDF. Try exporting your resume as text-based PDF, "
            "or paste the resume text instead."
        ) from exc

    text = "\n".join(pages).strip()
    if len(text) < 40:
        raise ValueError(
            "No selectable text was found in that PDF. If it is a scan or image, "
            "paste your resume text instead."
        )
    return text


# ---------------------------------------------------------------------------
# Heuristic (deterministic) extraction
# ---------------------------------------------------------------------------


def split_sections(text: str) -> dict[str, list[str]]:
    """Split resume text into ``{section: lines}`` using heading detection.

    Content lines keep their original indentation (leading whitespace) because
    the project/experience parsers use it to tell a new entry from the
    continuation of a wrapped bullet.
    """
    sections: dict[str, list[str]] = {}
    current = "header"
    for raw_line in text.splitlines():
        line = raw_line.rstrip("\r\n")
        stripped = line.strip()
        if not stripped:
            continue
        heading_match = _HEADING_RE.match(stripped.rstrip(":"))
        if heading_match:
            label = heading_match.group(1).strip().lower()
            matched_section = None
            for section, aliases in SECTION_ALIASES.items():
                if label in aliases or any(label.startswith(alias) for alias in aliases):
                    matched_section = section
                    break
            if matched_section:
                current = matched_section
                sections.setdefault(current, [])
                continue
        sections.setdefault(current, []).append(line)
    return sections


def _iter_section_lines(lines: list[str]) -> list[tuple[str, bool, bool]]:
    """Yield ``(stripped, indented, is_bullet)`` for each content line."""
    result: list[tuple[str, bool, bool]] = []
    for raw in lines:
        stripped = raw.strip()
        if not stripped:
            continue
        indented = raw[:1] in (" ", "\t")
        result.append((stripped, indented, bool(_BULLET_RE.match(stripped))))
    return result


def _clean_bullet(line: str) -> str:
    return _BULLET_RE.sub("", line).strip()


def _find_known_skills(text: str) -> list[str]:
    """Find known skills mentioned in text, ordered by where they appear."""
    found: list[tuple[int, str]] = []
    lowered = text.lower()
    for canonical in KNOWN_SKILLS:
        needle = canonical.lower()
        if needle.startswith(("c++", "c#", ".net")):
            pattern = re.escape(needle)
        else:
            pattern = r"(?<![a-z0-9+#])" + re.escape(needle) + r"(?![a-z0-9+#])"
        match = re.search(pattern, lowered)
        if match:
            found.append((match.start(), canonical))

    ordered: list[str] = []
    seen: set[str] = set()
    for _position, canonical in sorted(found, key=lambda item: item[0]):
        key = normalize_skill(canonical)
        if key and key not in seen:
            seen.add(key)
            ordered.append(canonical)
    return ordered


def _extract_name(text: str) -> str:
    """Take the first plausible human name from the top of the resume."""
    for line in text.splitlines()[:8]:
        candidate = line.strip()
        if not candidate:
            continue
        if candidate.lower().startswith(("name:", "resume", "curriculum")):
            value = candidate.split(":", 1)[1].strip() if ":" in candidate else ""
            if value:
                return value
            continue
        if any(marker in candidate.lower() for marker in ("@", "http", "+91", "phone", "email")):
            continue
        if re.search(r"\d", candidate):
            continue
        words = candidate.replace(",", " ").split()
        if 1 < len(words) <= 5 and all(word[0].isalpha() for word in words if word):
            if all(len(word) <= 22 for word in words):
                return candidate.title() if candidate.isupper() else candidate
    return ""


def _extract_education(text: str, sections: dict[str, list[str]]) -> Education:
    """Pull degree, college and year out of the education section."""
    lines = sections.get("education") or []

    degree = ""
    degree_pattern = re.compile(
        r"(B\.?\s?Tech|B\.?\s?E\.?|B\.?\s?Sc|M\.?\s?Tech|M\.?\s?Sc|BCA|MCA|Bachelor[^,]*)",
        re.IGNORECASE,
    )
    for line in lines or text.splitlines():
        match = degree_pattern.search(line)
        if match:
            degree = match.group(1).strip().rstrip(",")
            # Extend with the subject: "B.Tech in Computer Science and Engineering".
            lowered_line = line.lower()
            if " in " in lowered_line:
                tail = line[lowered_line.index(" in ") + 4 :]
                for separator in (",", " at ", " |", "("):
                    if separator in tail:
                        tail = tail.split(separator)[0]
                tail = tail.strip(" .;-")
                if 2 <= len(tail) <= 60:
                    degree = f"{degree} in {tail}"
            break

    college = ""
    college_re = re.compile(
        r"([A-Z][A-Za-z.&' ]{2,60}?(?:Institute|College|University|IIT|NIT|IIIT|BITS|VIT|Manipal|School)[A-Za-z.&' ]{0,40})"
    )
    for line in lines or text.splitlines():
        match = college_re.search(line)
        if match:
            college = re.sub(r"\s+", " ", match.group(1)).strip(" ,|-")
            break
    if not college:
        for line in text.splitlines():
            match = college_re.search(line)
            if match:
                college = re.sub(r"\s+", " ", match.group(1)).strip(" ,|-")
                break

    year = ""
    year_re = re.compile(
        r"\b((?:first|second|third|fourth|final|1st|2nd|3rd|4th)\s*(?:year|yr))\b", re.IGNORECASE
    )
    for line in lines or text.splitlines():
        match = year_re.search(line)
        if match:
            year = match.group(1).strip().title()
            break
    if not year:
        grad = re.search(r"\b(?:graduat\w*|expected|batch of|class of)\D{0,12}(20\d{2})\b", text, re.IGNORECASE)
        if grad:
            year = f"Expected {grad.group(1)}"
    if not year:
        cgpa = re.search(r"\bCGPA\b[^\n]{0,30}", text, re.IGNORECASE)
        year = ""
        if cgpa:
            year = ""
    return Education(degree=degree, college=college, year=year)


def _extract_skills(sections: dict[str, list[str]], text: str) -> list[str]:
    """Collect skills from the skills section, then anywhere in the resume."""
    skills: list[str] = []
    seen: set[str] = set()

    for raw in sections.get("skills", []):
        for token in _SPLIT_SKILLS_RE.split(_clean_bullet(raw)):
            # Handle labelled lines such as "Languages: Python, JavaScript".
            token = token.split(":")[-1]
            # Annotations like "(basic)" are metadata, not part of the skill name.
            token = re.sub(r"\([^)]*\)", "", token).strip(" .:()")
            if not token or len(token) > 40:
                continue
            canonical = _KNOWN_NORMALISED.get(normalize_skill(token))
            if canonical and normalize_skill(canonical) not in seen:
                seen.add(normalize_skill(canonical))
                skills.append(canonical)

    if len(skills) < 3:
        for canonical in _find_known_skills(text):
            if normalize_skill(canonical) not in seen:
                seen.add(normalize_skill(canonical))
                skills.append(canonical)

    return skills


def _extract_projects(sections: dict[str, list[str]]) -> list[Project]:
    """Turn the projects section into structured project entries.

    A non-indented, non-bullet line starts a new project (for example
    ``"CampusHire - Next.js and FastAPI job board"``); bullets and indented
    continuation lines belong to the project above them.
    """
    lines = _iter_section_lines(sections.get("projects", []))
    if not lines:
        return []

    blocks: list[tuple[str, list[str]]] = []
    title: str | None = None
    parts: list[str] = []

    for stripped, indented, is_bullet in lines:
        cleaned = _clean_bullet(stripped)
        if is_bullet or (indented and title is not None):
            parts.append(cleaned)
            continue
        if title is not None:
            blocks.append((title, parts))
        title = cleaned
        parts = []

    if title is not None:
        blocks.append((title, parts))

    projects: list[Project] = []
    for heading, body in blocks:
        name = heading
        summary_parts: list[str] = []

        split_match = re.split(r"\s+[—–]\s+|\s+-\s+|\s*:\s+", heading, maxsplit=1)
        if len(split_match) == 2 and len(split_match[0].strip()) <= 70:
            name = split_match[0].strip()
            summary_parts.append(split_match[1].strip())
        elif len(heading) <= 70 and body:
            name = heading.strip()
        else:
            name = heading[:60].strip()

        summary_parts.extend(part for part in body if part)
        summary = ". ".join(
            part.rstrip(". ") for part in summary_parts if part.strip()
        ).strip()
        tech = _find_known_skills(f"{heading} {summary}")

        projects.append(
            Project(
                name=re.sub(r"\s+", " ", name).strip()[:90],
                summary=re.sub(r"\s+", " ", summary).strip()[:400],
                tech=tech[:10],
            )
        )
    return projects[:6]


def _extract_experience(sections: dict[str, list[str]]) -> list[str]:
    """Build one-line experience entries: ``"Role, Company: achievement"``.

    Keeping the role/company in front of each achievement means a bullet still
    cites where the work happened, which is what an application reader needs.
    """
    lines = _iter_section_lines(sections.get("experience", []))
    blocks: list[tuple[str | None, list[str]]] = []
    heading: str | None = None
    bullets: list[str] = []

    for stripped, indented, is_bullet in lines:
        cleaned = _clean_bullet(stripped)
        if is_bullet:
            bullets.append(cleaned)
        elif indented and bullets:
            bullets[-1] = f"{bullets[-1]} {cleaned}"
        else:
            if heading is not None or bullets:
                blocks.append((heading, bullets))
            heading = re.sub(r"\([^)]*\)", "", cleaned).strip(" ,-")
            bullets = []
    if heading is not None or bullets:
        blocks.append((heading, bullets))

    entries: list[str] = []
    for block_heading, block_bullets in blocks:
        for bullet in block_bullets:
            entry = f"{block_heading}: {bullet}" if block_heading else bullet
            entries.append(re.sub(r"\s+", " ", entry).strip())
    if not entries:
        entries = [
            re.sub(r"\s+", " ", block_heading).strip()
            for block_heading, _ in blocks
            if block_heading
        ]
    return [entry[:320] for entry in entries if entry][:6]


def _extract_interests(sections: dict[str, list[str]]) -> list[str]:
    """Split the interests section into individual short interests."""
    interests: list[str] = []
    for raw in sections.get("interests", []):
        cleaned = _clean_bullet(raw).rstrip(".")
        for part in re.split(r",|;| and ", cleaned):
            value = part.strip(" .")
            if 2 <= len(value) <= 60 and value not in interests:
                interests.append(value)
    return interests[:8]


def _extract_list_section(sections: dict[str, list[str]], name: str, limit: int = 6) -> list[str]:
    """Return cleaned bullet lines from a list-like section."""
    values: list[str] = []
    for line in sections.get(name, []):
        cleaned = _clean_bullet(line)
        if cleaned and len(cleaned) > 3:
            values.append(cleaned[:220])
    return values[:limit]


def _infer_target_types(text: str) -> list[str]:
    """Guess which opportunity types the student is aiming for."""
    lowered = text.lower()
    found: list[str] = []
    if re.search(r"\bintern(?:ship)?s?\b", lowered):
        found.append("internship")
    if "hackathon" in lowered:
        found.append("hackathon")
    if "scholarship" in lowered or "fellowship" in lowered:
        found.append("scholarship")
    if re.search(r"\b(?:full[- ]time|new grad|placement)\b", lowered):
        found.append("job")
    # A student with internships/projects is primarily hunting internships.
    if "internship" in found:
        return found
    return found or ["internship"]


def _infer_location(text: str) -> str:
    """Pick the first Indian city mentioned, preferring a stated preference."""
    preference = re.search(r"(?:preferred location|location preference|preferred|open to relocating to)[:\s]+([A-Za-z ]{3,30})", text, re.IGNORECASE)
    if preference:
        value = preference.group(1).strip()
        for city in INDIAN_CITIES:
            if city.lower() in value.lower():
                return city
    for city in INDIAN_CITIES:
        if re.search(rf"\b{re.escape(city)}\b", text, re.IGNORECASE):
            return city
    return ""


def heuristic_profile(text: str) -> dict[str, Any]:
    """Deterministic resume -> profile extraction (no network, no model).

    Used both as the LLM fallback and for mock mode. Returns a plain dict that
    :class:`ProfileExtraction` validates.
    """
    sections = split_sections(text)
    header_text = "\n".join(sections.get("header", []))
    return {
        "name": _extract_name(text),
        "education": _extract_education(text, sections).model_dump(),
        "skills": _extract_skills(sections, text),
        "projects": [project.model_dump() for project in _extract_projects(sections)],
        "experience": _extract_experience(sections),
        "interests": _extract_interests(sections),
        "target_types": _infer_target_types(text + "\n" + header_text),
        "location_pref": _infer_location(text),
    }


# ---------------------------------------------------------------------------
# Public async API
# ---------------------------------------------------------------------------


async def parse_profile(raw_text: str, *, client: LLMClient | None = None) -> tuple[StudentProfile, bool, str | None]:
    """Extract a :class:`StudentProfile` from resume text.

    Returns:
        ``(profile, ai_available, note)``. ``ai_available`` is False whenever the
        deterministic extractor produced the profile.
    """
    text = (raw_text or "").strip()
    if len(text) < 30:
        raise ValueError("Resume text is too short to extract a profile from.")

    client = client or get_llm_client()
    result = await client.complete_json(
        task="profile_extraction",
        system=prompts.PROFILE_EXTRACTION_SYSTEM,
        user=prompts.PROFILE_EXTRACTION_USER.format(resume_text=text[:12_000]),
        schema=ProfileExtraction,
        fallback=lambda: heuristic_profile(text),
        max_tokens=2500,
    )

    extraction = result.value
    if not extraction.skills and not extraction.projects and not extraction.name:
        # The model returned nothing useful - deterministic extraction is better.
        extraction = ProfileExtraction.model_validate(heuristic_profile(text))
        return (
            StudentProfile(**extraction.model_dump(), raw_text=text),
            False,
            "AI returned an empty profile, so a rule-based parse was used instead.",
        )

    profile = StudentProfile(**extraction.model_dump(), raw_text=text)
    return profile, result.ai_available, result.note


def load_sample_resume() -> str:
    """Read the bundled sample resume used by the demo button."""
    if SAMPLE_RESUME_PATH.exists():
        text = SAMPLE_RESUME_PATH.read_text(encoding="utf-8").strip()
        if len(text) > 80:
            return text
    logger.warning("Sample resume file missing; using built-in fallback")
    return _BUILTIN_SAMPLE_RESUME


async def parse_resume_bytes(data: bytes) -> tuple[StudentProfile, bool, str | None, str]:
    """Parse an uploaded PDF into a profile.

    Returns:
        ``(profile, ai_available, note, raw_text)``.
    """
    text = extract_text_from_pdf(data)
    profile, ai_available, note = await parse_profile(text)
    return profile, ai_available, note, text


_BUILTIN_SAMPLE_RESUME = """YASH AERON
Meerut, Uttar Pradesh, India | aeronyash2020@gmail.com | +91-9548579883
github.com/yash-aeron | linkedin.com/in/yash-aeron-688ab8269

EDUCATION
B.Tech in Computer Science & Engineering, Graphic Era University
Expected 2028 | CGPA: 9.00 / 10

SKILLS
Python, TypeScript, JavaScript, C++, Java, React, FastAPI, Node.js, SQL, PostgreSQL,
Docker, Redis, MongoDB, Git, RAG, Agentic AI, Prompt Engineering, scikit-learn, AWS

EXPERIENCE
Software Engineering & Autonomous Systems (2024 - Present)
- Built SentinelPay: an idempotent, concurrency-safe payment processing engine with a PostgreSQL double-entry ledger and fraud scoring with Redis velocity windows.
- Developed BlackBox: an autonomous web agent that learns and reuses web-app state transitions from DOM and accessibility trees.

PROJECTS
SentinelPay — Payments & Fraud Risk Engine with PostgreSQL double-entry ledger, Redis velocity scoring, and RAG compliance copilot.
BlackBox — Autonomous Web Agent with Persistent Behavioral Model that learns and reuses web-app state transitions from DOM and accessibility trees.
Miniroute — Local AI Gateway with Automatic Failover, retry handling, circuit breakers, and streaming failover.

CERTIFICATIONS
- Machine Learning Specialization – DeepLearning.AI & Stanford University
- AWS Cloud Practitioner Essentials (100%)
- AWS CI/CD & Cloud Networking

INTERESTS
Puzzles, Chess, Music, FinTech, Distributed Systems, AI Agents
"""


# ---------------------------------------------------------------------------
# Compatibility shim: this file is named `profile.py`, which would otherwise
# shadow CPython's stdlib `profile` module. PyTorch reaches it through
# `cProfile` (`torch.distributed.checkpoint` -> `import cProfile` -> stdlib
# `profile`), so without this shim importing sentence-transformers fails with
# "Could not import module 'PreTrainedModel'". PEP 562 module `__getattr__`
# delegates any attribute this module does not define to the real stdlib module.
# ---------------------------------------------------------------------------

_STDLIB_PROFILE_PATH = Path(sysconfig.get_paths()["stdlib"]) / "profile.py"
_stdlib_profile: ModuleType | None = None


def _load_stdlib_profile() -> ModuleType:
    """Load CPython's own ``profile`` module by path (bypassing this file)."""
    global _stdlib_profile
    if _stdlib_profile is None:
        spec = importlib.util.spec_from_file_location("_stdlib_profile", _STDLIB_PROFILE_PATH)
        if spec is None or spec.loader is None:  # pragma: no cover - exotic installs
            raise AttributeError("stdlib profile module is unavailable")
        module = importlib.util.module_from_spec(spec)
        sys.modules.setdefault("_stdlib_profile", module)
        spec.loader.exec_module(module)
        _stdlib_profile = module
    return _stdlib_profile


def __getattr__(name: str) -> Any:
    """Delegate stdlib ``profile`` attributes such as ``run`` and ``Profile``."""
    if name.startswith("__"):
        raise AttributeError(name)
    return getattr(_load_stdlib_profile(), name)

