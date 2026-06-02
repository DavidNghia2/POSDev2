import { serve } from "https://deno.land/std@0.224.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

function roleNameFromProfile(profile: Record<string, unknown>): string | undefined {
  const roles = profile.roles as { name?: string } | { name?: string }[] | undefined;
  if (Array.isArray(roles)) {
    return roles[0]?.name;
  }
  return roles?.name;
}

serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  try {
    const supabaseUrl = Deno.env.get("SUPABASE_URL") ?? "";
    const anonKey = Deno.env.get("SUPABASE_ANON_KEY") ?? "";
    const serviceRoleKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
    const authHeader = req.headers.get("Authorization") ?? "";
    const body = await req.json();

    const userClient = createClient(supabaseUrl, anonKey, {
      global: { headers: { Authorization: authHeader } },
    });
    const adminClient = createClient(supabaseUrl, serviceRoleKey);

    const { data: callerData, error: callerError } = await userClient.auth.getUser();
    if (callerError || !callerData.user) {
      throw new Error("Unauthorized");
    }

    const { data: callerProfile, error: profileError } = await adminClient
      .from("profiles")
      .select("store_id, roles(name)")
      .eq("auth_user_id", callerData.user.id)
      .single();
    if (profileError || !callerProfile || roleNameFromProfile(callerProfile) !== "Admin") {
      throw new Error("Only store admins can create users");
    }

    const { data: role, error: roleError } = await adminClient
      .from("roles")
      .select("id")
      .eq("name", body.role_name)
      .single();
    if (roleError || !role) {
      throw new Error("Invalid role");
    }

    const { data: created, error: createError } = await adminClient.auth.admin.createUser({
      email: body.email,
      password: body.password,
      email_confirm: true,
      user_metadata: { full_name: body.full_name },
    });
    if (createError || !created.user) {
      throw createError ?? new Error("Could not create auth user");
    }

    const { data: profile, error: upsertError } = await adminClient
      .from("profiles")
      .upsert({
        auth_user_id: created.user.id,
        store_id: callerProfile.store_id,
        email: body.email,
        full_name: body.full_name,
        role_id: role.id,
        active: true,
        updated_at: new Date().toISOString(),
      })
      .select("auth_user_id,store_id,email,full_name,role_id,active,deleted_at,roles(id,name,permissions),stores(id,name)")
      .single();
    if (upsertError) {
      throw upsertError;
    }

    return new Response(JSON.stringify({ profile }), {
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  } catch (error) {
    return new Response(JSON.stringify({ error: String(error?.message ?? error) }), {
      status: 400,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }
});
