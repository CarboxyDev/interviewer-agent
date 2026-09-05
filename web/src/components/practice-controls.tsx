import {
  ArrowRight,
  Check,
  Download,
  FileText,
  HelpCircle,
  Mic,
  MicOff,
  Pause,
  Play,
  RotateCcw,
  Square,
  Trash2,
  Volume2,
  type LucideIcon,
} from "lucide-react";
import { Button } from "./ui/button";
import { Checkbox } from "./ui/checkbox";
import { Label } from "./ui/label";
import { useRoom } from "@/lib/practice-context";

const icons: Record<string, LucideIcon> = {
  configure: ArrowRight,
  ready: ArrowRight,
  begin: Play,
  mic: Check,
  mute: MicOff,
  repeat: RotateCcw,
  pause: Pause,
  end: Square,
  help: HelpCircle,
  withdraw: Trash2,
  delete: Trash2,
  "confirm-delete": Trash2,
  retry: RotateCcw,
  next: ArrowRight,
  "sample-answer": Play,
  finish: ArrowRight,
  review: FileText,
  export: Download,
  "evidence-gap": FileText,
  "evidence-strength": FileText,
  recover: RotateCcw,
};
export function Action({
  action,
  children,
  variant = "default",
  disabled = false,
}: {
  action: string;
  children: React.ReactNode;
  variant?: "default" | "outline" | "ghost";
  disabled?: boolean;
}) {
  const { act, state } = useRoom();
  const Icon =
    action === "mute" && state.muted
      ? Mic
      : action === "pause" && state.voice === "paused"
        ? Play
        : action === "repeat"
          ? Volume2
          : icons[action];
  return (
    <Button
      type="button"
      data-action={action}
      variant={variant}
      className="min-h-11 h-auto whitespace-normal py-2.5"
      disabled={disabled}
      onClick={() => act(action)}
    >
      {Icon && <Icon aria-hidden="true" />}
      {children}
    </Button>
  );
}
export function Choice({
  id,
  checked,
  disabled,
  label,
  description,
  onChange,
}: {
  id: string;
  checked: boolean;
  disabled?: boolean;
  label: string;
  description: string;
  onChange: (value: boolean) => void;
}) {
  return (
    <div className="choice">
      <Checkbox
        id={id}
        checked={checked}
        disabled={disabled}
        onCheckedChange={(value) => onChange(value === true)}
        className="mt-1"
      />
      <Label htmlFor={id} className="block leading-6">
        <span>{label}</span>
        <small>{description}</small>
      </Label>
    </div>
  );
}
