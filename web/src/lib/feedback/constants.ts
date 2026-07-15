export const FEEDBACK_TYPES = [
  "valid",
  "false_positive",
  "important",
  "ignore",
  "brand_candidate",
  "price_watch",
  "content_opportunity",
] as const;

export type FeedbackType = (typeof FEEDBACK_TYPES)[number];

export const FEEDBACK_LABELS: Record<FeedbackType, string> = {
  valid: "有效 Deal",
  false_positive: "误报",
  important: "重要",
  ignore: "忽略",
  brand_candidate: "新竞品候选",
  price_watch: "价格关注",
  content_opportunity: "内容机会",
};

export interface FeedbackActionState {
  ok: boolean;
  message: string;
}

export const initialFeedbackState: FeedbackActionState = {
  ok: false,
  message: "",
};
