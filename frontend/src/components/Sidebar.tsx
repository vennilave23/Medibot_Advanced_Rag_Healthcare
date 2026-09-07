import type { Role } from "@/lib/api";

const ROLE_LABEL: Record<Role, string> = {
  doctor: "Doctor",
  nurse: "Nurse",
  billing_executive: "Billing Executive",
  technician: "Technician",
  admin: "Admin",
};

export function Sidebar({
  username,
  role,
  collections,
  onLogout,
}: {
  username: string;
  role: Role;
  collections: string[];
  onLogout: () => void;
}) {
  return (
    <aside className="flex w-64 shrink-0 flex-col border-r border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
      <div>
        <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-50">MediBot</h2>
        <p className="text-xs text-slate-400">MediAssist Health Network</p>
      </div>

      <div className="mt-6">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Signed in as</p>
        <p className="mt-1 text-sm font-medium text-slate-800 dark:text-slate-100">{username}</p>
        <span className="mt-2 inline-block rounded-full bg-blue-100 px-2.5 py-1 text-xs font-semibold text-blue-700 dark:bg-blue-950 dark:text-blue-300">
          {ROLE_LABEL[role]}
        </span>
      </div>

      <div className="mt-6 flex-1">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Accessible collections</p>
        <ul className="mt-2 space-y-1">
          {collections.map((collection) => (
            <li
              key={collection}
              className="rounded-md bg-slate-100 px-2.5 py-1 text-xs capitalize text-slate-600 dark:bg-slate-800 dark:text-slate-300"
            >
              {collection}
            </li>
          ))}
        </ul>
      </div>

      <button
        onClick={onLogout}
        className="mt-4 rounded-md border border-slate-200 px-3 py-2 text-sm text-slate-600 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
      >
        Log out
      </button>
    </aside>
  );
}
