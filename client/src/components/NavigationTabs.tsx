/**
 * Bottom / top navigation tabs for switching views.
 */


export type ActiveTab = 'counter' | 'customers' | 'history' | 'fixtures';

interface NavigationTabsProps {
  activeTab: ActiveTab;
  onTabChange: (tab: ActiveTab) => void;
}

export function NavigationTabs({ activeTab, onTabChange }: NavigationTabsProps) {
  const tabs: { id: ActiveTab; label: string }[] = [
    { id: 'counter', label: 'کاؤنٹر (Counter)' },
    { id: 'customers', label: 'کھاتے (Ledgers)' },
    { id: 'history', label: 'اندراجات (History)' },
    { id: 'fixtures', label: 'فکسچرز' },
  ];

  return (
    <nav className="flex items-center gap-1.5 p-1 bg-gray-900 border border-gray-800 rounded-2xl mb-4 overflow-x-auto">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          type="button"
          onClick={() => onTabChange(tab.id)}
          className={`flex-1 min-w-[75px] py-1.5 px-2 rounded-xl text-xs font-nastaliq transition-all whitespace-nowrap text-center ${
            activeTab === tab.id
              ? 'bg-emerald-600 text-white font-semibold shadow-md'
              : 'text-gray-400 hover:text-gray-200 hover:bg-gray-850'
          }`}
        >
          {tab.label}
        </button>
      ))}
    </nav>
  );
}

