import React from "react";
import {
  Radar,
  Sparkles,
  ChevronDown,
  ArrowRight,
  ArrowLeft,
  Check,
  X,
  AlertTriangle,
  Shield,
  Copy,
  Calendar,
  Upload,
  FileText,
  MapPin,
  Building,
  Clock,
  ExternalLink,
  RefreshCw,
  Trash2,
  Plus,
  Info,
  Target,
  Filter,
  Link as LinkIcon,
  Search,
  CheckCircle2,
  AlertCircle,
  GraduationCap,
  Zap,
  SlidersHorizontal,
  Bookmark,
  Share2,
  Download,
  LucideProps,
} from "lucide-react";

export type IconName =
  | "radar"
  | "sparkles"
  | "chevronDown"
  | "arrowRight"
  | "arrowLeft"
  | "check"
  | "x"
  | "alert"
  | "shield"
  | "copy"
  | "calendar"
  | "upload"
  | "file"
  | "mapPin"
  | "building"
  | "clock"
  | "external"
  | "refresh"
  | "trash"
  | "plus"
  | "info"
  | "target"
  | "filter"
  | "link"
  | "search"
  | "checkCircle"
  | "alertCircle"
  | "cap"
  | "zap"
  | "sliders"
  | "bookmark"
  | "share"
  | "download";

const ICON_MAP: Record<IconName, React.ComponentType<LucideProps>> = {
  radar: Radar,
  sparkles: Sparkles,
  chevronDown: ChevronDown,
  arrowRight: ArrowRight,
  arrowLeft: ArrowLeft,
  check: Check,
  x: X,
  alert: AlertTriangle,
  shield: Shield,
  copy: Copy,
  calendar: Calendar,
  upload: Upload,
  file: FileText,
  mapPin: MapPin,
  building: Building,
  clock: Clock,
  external: ExternalLink,
  refresh: RefreshCw,
  trash: Trash2,
  plus: Plus,
  info: Info,
  target: Target,
  filter: Filter,
  link: LinkIcon,
  search: Search,
  checkCircle: CheckCircle2,
  alertCircle: AlertCircle,
  cap: GraduationCap,
  zap: Zap,
  sliders: SlidersHorizontal,
  bookmark: Bookmark,
  share: Share2,
  download: Download,
};

interface IconProps extends LucideProps {
  name: IconName;
}

export function Icon({ name, strokeWidth = 2, ...props }: IconProps) {
  const Component = ICON_MAP[name] ?? Sparkles;
  return <Component strokeWidth={strokeWidth} {...props} />;
}
