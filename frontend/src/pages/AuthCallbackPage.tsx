import { useEffect, useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import { useAuth } from "@/hooks/useAuth";

/**
 * OAuth callback handler.
 * Receives token from URL, stores it, fetches user, and redirects.
 */
export default function AuthCallbackPage() {
  const navigate = useNavigate();
  const fetchUser = useAuth((s) => s.fetchUser);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const token = params.get("token");
    const errorParam = params.get("error");

    if (errorParam) {
      const errorMessages: Record<string, string> = {
        oauth_failed: "Google sign-in failed. Please try again.",
        domain_not_allowed: "Your email domain is not authorized. Contact your administrator for an invite.",
        max_users_reached: "Maximum user limit reached. Contact your administrator.",
      };
      setError(errorMessages[errorParam] || "Authentication failed. Please try again.");
      setTimeout(() => navigate({ to: "/login" }), 3000);
      return;
    }

    if (!token) {
      setError("No authentication token received.");
      setTimeout(() => navigate({ to: "/login" }), 2000);
      return;
    }

    // Store the token
    localStorage.setItem("access_token", token);
    
    // Fetch user and redirect
    fetchUser()
      .then(() => {
        navigate({ to: "/" });
      })
      .catch(() => {
        localStorage.removeItem("access_token");
        setError("Failed to verify authentication. Please try again.");
        setTimeout(() => navigate({ to: "/login" }), 2000);
      });
  }, [navigate, fetchUser]);

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-secondary">
        <div className="text-center p-8">
          <div className="text-red-600 text-lg font-medium mb-2">{error}</div>
          <div className="text-muted-foreground text-sm">Redirecting to login...</div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-secondary">
      <div className="text-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[#253a52] mx-auto mb-4"></div>
        <div className="text-muted-foreground">Completing sign-in...</div>
      </div>
    </div>
  );
}
