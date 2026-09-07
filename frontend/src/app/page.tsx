"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { login as loginRequest, type Role } from "@/lib/api";
import { useSession } from "@/contexts/SessionContext";

const DEMO_ACCOUNTS: { username: string; password: string; role: Role; label: string }[] = [
  { username: "dr.mehta", password: "doctor", role: "doctor", label: "Dr. Mehta — Doctor" },
  { username: "nurse.priya", password: "nurse", role: "nurse", label: "Nurse Priya — Nurse" },
  {
    username: "billing.ravi",
    password: "billing_executive",
    role: "billing_executive",
    label: "Billing Ravi — Billing Executive",
  },
  { username: "tech.anand", password: "technician", role: "technician", label: "Tech Anand — Technician" },
  { username: "admin.sys", password: "admin", role: "admin", label: "Admin — Admin" },
];

export default function LoginPage() {
  const router = useRouter();
  const { login } = useSession();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function attemptLogin(u: string, p: string) {
    setError(null);
    setIsSubmitting(true);
    try {
      const res = await loginRequest(u, p);
      login({ username: u, role: res.role, token: res.token });
      router.push("/chat");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setIsSubmitting(false);
    }
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    void attemptLogin(username, password);
  }

  return (
    <div className="flex flex-1 items-center justify-center bg-slate-50 px-4 py-12 dark:bg-slate-950">
      <div className="w-full max-w-md space-y-8">
        <div className="text-center">
          <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-50">MediBot</h1>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            Internal assistant for MediAssist Health Network staff
          </p>
        </div>

        <form
          onSubmit={handleSubmit}
          className="space-y-4 rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900"
        >
          <div>
            <label htmlFor="username" className="block text-sm font-medium text-slate-700 dark:text-slate-300">
              Username
            </label>
            <input
              id="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none dark:border-slate-700 dark:bg-slate-800 dark:text-slate-50"
            />
          </div>
          <div>
            <label htmlFor="password" className="block text-sm font-medium text-slate-700 dark:text-slate-300">
              Password
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none dark:border-slate-700 dark:bg-slate-800 dark:text-slate-50"
            />
          </div>

          {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}

          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {isSubmitting ? "Signing in..." : "Sign in"}
          </button>
        </form>

        <div>
          <p className="mb-2 text-center text-xs font-medium uppercase tracking-wide text-slate-400">
            Or try a demo account
          </p>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {DEMO_ACCOUNTS.map((account) => (
              <button
                key={account.username}
                type="button"
                disabled={isSubmitting}
                onClick={() => void attemptLogin(account.username, account.password)}
                className="rounded-md border border-slate-200 bg-white px-3 py-2 text-left text-xs text-slate-700 hover:border-blue-400 hover:bg-blue-50 disabled:opacity-50 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300 dark:hover:bg-slate-800"
              >
                {account.label}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
