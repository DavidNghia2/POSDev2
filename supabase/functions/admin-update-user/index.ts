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
      throw new Error("Only store admins can update users");
    }

    const { data: targetProfile, error: targetError } = await adminClient
      .from("profiles")
      .select("auth_user_id,store_id,role_id,roles(name)")
      .eq("auth_user_id", body.auth_user_id)
      .single();
    if (targetError || !targetProfile || targetProfile.store_id !== callerProfile.store_id) {
      throw new Error("Target user is not in this store");
    }

    if (targetProfile.auth_user_id === callerData.user.id && body.active === false) {
      throw new Error("You cannot deactivate your own account");
    }

    const { data: role, error: roleError } = await adminClient
      .from("roles")
      .select("id,name")
      .eq("name", body.role_name)
      .single();
    if (roleError || !role) {
      throw new Error("Invalid role");
    }

    const { count: activeAdminCount, error: countError } = await adminClient
      .from("profiles")
      .select("auth_user_id, roles!inner(name)", { count: "exact", head: true })
      .eq("store_id", callerProfile.store_id)
      .eq("active", true)
      .eq("roles.name", "Admin");
    if (countError) {
      throw countError;
    }
    if (roleNameFromProfile(targetProfile) === "Admin" && role.name !== "Admin" && (activeAdminCount ?? 0) <= 1) {
      throw new Error("Cannot remove the last active admin from this store");
    }

    const authUpdates: Record<string, unknown> = {
      email: body.email,
      user_metadata: { full_name: body.full_name },
    };
    if (body.password) {
      authUpdates.password = body.password;
    }
    const { error: authUpdateError } = await adminClient.auth.admin.updateUserById(
      body.auth_user_id,
      authUpdates,
    );
    if (authUpdateError) {
      throw authUpdateError;
    }

    const { data: profile, error: updateError } = await adminClient
      .from("profiles")
      .update({
        email: body.email,
        full_name: body.full_name,
        role_id: role.id,
        active: body.active !== false,
        updated_at: new Date().toISOString(),
      })
      .eq("auth_user_id", body.auth_user_id)
      .eq("store_id", callerProfile.store_id)
      .select("auth_user_id,store_id,email,full_name,role_id,active,roles(id,name,permissions),stores(id,name)")
      .single();
    if (updateError) {
      throw updateError;
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
