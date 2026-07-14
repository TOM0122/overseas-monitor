import "server-only";

import { createClient, type SupabaseClient } from "@supabase/supabase-js";

let readClient: SupabaseClient | null = null;
let adminClient: SupabaseClient | null = null;

function getUrl(): string {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  if (!url) throw new Error("未配置 NEXT_PUBLIC_SUPABASE_URL");
  return url;
}

export function getSupabaseReadClient(): SupabaseClient {
  if (readClient) return readClient;
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY ?? process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!key) throw new Error("未配置 SUPABASE_SERVICE_ROLE_KEY 或 NEXT_PUBLIC_SUPABASE_ANON_KEY");
  readClient = createClient(getUrl(), key, {
    auth: { persistSession: false, autoRefreshToken: false },
  });
  return readClient;
}

export function getSupabaseAdminClient(): SupabaseClient {
  if (adminClient) return adminClient;
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!key) throw new Error("Feedback 写入需要 SUPABASE_SERVICE_ROLE_KEY");
  adminClient = createClient(getUrl(), key, {
    auth: { persistSession: false, autoRefreshToken: false },
  });
  return adminClient;
}

export function getOffsiteDealsTable(): string {
  const table = process.env.OFFSITE_DEALS_TABLE || "slickdeals_deals";
  if (!/^[a-z_][a-z0-9_]*$/i.test(table)) throw new Error("OFFSITE_DEALS_TABLE 格式无效");
  return table;
}
