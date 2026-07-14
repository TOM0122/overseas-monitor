import { ClipboardButton } from "@/components/ui/ClipboardButton";
import { FeedbackDialog } from "@/components/deals/FeedbackDialog";

export function DealFeedbackButtons({ dealId, title, url }: { dealId: string; title: string; url?: string | null }) {
  return (
    <div className="flex items-center gap-2">
      <FeedbackDialog dealId={dealId} title={title} />
      {url ? <ClipboardButton text={url} label="复制链接" compact /> : null}
    </div>
  );
}
