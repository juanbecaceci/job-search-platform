import { EmptyState } from "@/components/ui";

export default function Placeholder({ name }: { name: string }) {
  return (
    <div style={{ height: "100%", display: "flex", alignItems: "center", justifyContent: "center" }}>
      <EmptyState title={`${name}`} hint="This screen is being wired up next." />
    </div>
  );
}
