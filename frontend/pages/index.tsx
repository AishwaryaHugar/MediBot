import { useState, FormEvent } from "react";
import { useRouter } from "next/router";
import Head from "next/head";
import { login } from "../lib/api";

const DEMO_ACCOUNTS = [
  { username: "doctor_user",  role: "Doctor",             hint: "Clinical, Nursing, General" },
  { username: "nurse_user",   role: "Nurse",              hint: "Nursing, General" },
  { username: "billing_user", role: "Billing Executive",  hint: "Billing, General + SQL analytics" },
  { username: "tech_user",    role: "Technician",         hint: "Equipment, General" },
  { username: "admin_user",   role: "Admin",              hint: "All collections" },
];

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword]  = useState("");
  const [error, setError]        = useState("");
  const [loading, setLoading]    = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const data = await login(username, password);
      localStorage.setItem("medibot_token",       data.token);
      localStorage.setItem("medibot_role",        data.role);
      localStorage.setItem("medibot_username",    data.username);
      localStorage.setItem("medibot_collections", JSON.stringify(data.accessible_collections));
      router.push("/chat");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  }

  function fillDemo(u: string) {
    setUsername(u);
    setPassword("password123");
    setError("");
  }

  return (
    <>
      <Head><title>MediBot — Login</title></Head>
      <div className="min-h-screen bg-gradient-to-br from-brand-50 to-blue-100 flex items-center justify-center p-4">
        <div className="w-full max-w-4xl grid md:grid-cols-2 gap-8">

          {/* Login card */}
          <div className="bg-white rounded-2xl shadow-xl p-8 flex flex-col justify-center">
            <div className="mb-8">
              <div className="flex items-center gap-3 mb-2">
                <div className="w-10 h-10 bg-brand-600 rounded-xl flex items-center justify-center text-white font-bold text-lg">M</div>
                <h1 className="text-2xl font-bold text-gray-900">MediBot</h1>
              </div>
              <p className="text-gray-500 text-sm">MediAssist Health Network — Internal Knowledge Assistant</p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Username</label>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  required
                  className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500 text-sm"
                  placeholder="Enter username"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Password</label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500 text-sm"
                  placeholder="Enter password"
                />
              </div>

              {error && (
                <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-2">
                  {error}
                </div>
              )}

              <button
                type="submit"
                disabled={loading}
                className="w-full bg-brand-600 hover:bg-brand-700 disabled:opacity-50 text-white font-medium py-2.5 rounded-lg transition-colors text-sm"
              >
                {loading ? "Signing in…" : "Sign in"}
              </button>
            </form>
          </div>

          {/* Demo accounts panel */}
          <div className="bg-white rounded-2xl shadow-xl p-8">
            <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-4">Demo Accounts</h2>
            <p className="text-xs text-gray-400 mb-5">All accounts use password: <code className="bg-gray-100 px-1 py-0.5 rounded">password123</code></p>
            <div className="space-y-3">
              {DEMO_ACCOUNTS.map((acc) => (
                <button
                  key={acc.username}
                  onClick={() => fillDemo(acc.username)}
                  className="w-full text-left px-4 py-3 border border-gray-200 rounded-xl hover:border-brand-400 hover:bg-brand-50 transition-all group"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-gray-800 text-sm group-hover:text-brand-700">{acc.role}</span>
                    <span className="text-xs text-gray-400 font-mono">{acc.username}</span>
                  </div>
                  <p className="text-xs text-gray-500 mt-0.5">Access: {acc.hint}</p>
                </button>
              ))}
            </div>
          </div>

        </div>
      </div>
    </>
  );
}
