import { ThemePicker } from "@/components/theme-picker";
import { Button } from "@/components/ui/button";
import { ArrowRight } from "lucide-react";

export default function App() {
  return (
    <div className="mx-auto max-w-5xl p-8">
      <header className="flex items-center justify-between gap-4">
        <span className="text-xl font-semibold">Practice Room</span>
        <ThemePicker />
      </header>
      <main className="py-16">
        <h1 className="text-3xl font-semibold tracking-tight">
          Interview practice
        </h1>
        <p className="my-6 text-muted-foreground">
          Work through an interview question and review your answer.
        </p>
        <Button disabled>
          Set up practice
          <ArrowRight aria-hidden="true" />
        </Button>
      </main>
    </div>
  );
}
