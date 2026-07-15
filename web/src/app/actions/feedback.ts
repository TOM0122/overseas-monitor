"use server";

import { revalidatePath } from "next/cache";

import {
  FEEDBACK_TYPES,
  type FeedbackActionState,
  type FeedbackType,
} from "@/lib/feedback/constants";
import { createDealFeedback as insertDealFeedback } from "@/lib/queries/feedback";

export async function createDealFeedback(
  _previousState: FeedbackActionState,
  formData: FormData,
): Promise<FeedbackActionState> {
  try {
    const textField = (name: string, maxLength: number): string => {
      const value = String(formData.get(name) ?? "").trim();
      if (value.length > maxLength) throw new Error(`${name} 超过 ${maxLength} 个字符`);
      return value;
    };
    const dealId = textField("deal_id", 200);
    const feedbackType = textField("feedback_type", 40) as FeedbackType;
    const reason = textField("reason", 300);
    const note = textField("note", 1000);
    if (!dealId) return { ok: false, message: "缺少 Deal ID" };
    if (!FEEDBACK_TYPES.includes(feedbackType)) return { ok: false, message: "反馈类型无效" };

    await insertDealFeedback({
      deal_id: dealId,
      feedback_type: feedbackType,
      reason: reason || null,
      note: note || null,
      created_by: process.env.FEEDBACK_CREATED_BY || "web-console",
    });
    revalidatePath("/");
    revalidatePath("/deals");
    return { ok: true, message: "反馈已保存" };
  } catch (error) {
    console.error("Feedback write failed", error);
    return { ok: false, message: error instanceof Error ? error.message : "反馈保存失败" };
  }
}
