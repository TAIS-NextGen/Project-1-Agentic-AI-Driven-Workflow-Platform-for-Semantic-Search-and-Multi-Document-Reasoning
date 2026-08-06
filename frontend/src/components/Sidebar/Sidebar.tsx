import type { ReactNode } from 'react';
import { useWorkflowStore } from '../../store/workflowStore';
import { useFlowStore } from '../../store/flowStore';
import type { AppRoute, SidebarUser } from '../../types';
import type { AppTheme } from '../../App';
import styles from './Sidebar.module.css';

export interface SidebarProps {
  activeRoute: AppRoute;
  onNavigate: (route: AppRoute) => void;
  user?: SidebarUser;
  theme: AppTheme;
  onToggleTheme: () => void;
}

interface NavItemConfig {
  route: AppRoute;
  label: string;
  icon: ReactNode;
}

const DEFAULT_USER: SidebarUser = { name: 'Alex Morgan' };

const NAV_ITEMS: NavItemConfig[] = [
  {
    route: 'dashboard',
    label: 'Dashboard',
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
        <rect x="2" y="2" width="5" height="5" rx="1" stroke="currentColor" strokeWidth="1.25" />
        <rect x="9" y="2" width="5" height="5" rx="1" stroke="currentColor" strokeWidth="1.25" />
        <rect x="2" y="9" width="5" height="5" rx="1" stroke="currentColor" strokeWidth="1.25" />
        <rect x="9" y="9" width="5" height="5" rx="1" stroke="currentColor" strokeWidth="1.25" />
      </svg>
    ),
  },
  {
    route: 'workflows',
    label: 'Workflows',
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
        <circle cx="3.5" cy="8" r="1.75" stroke="currentColor" strokeWidth="1.25" />
        <circle cx="12.5" cy="4" r="1.75" stroke="currentColor" strokeWidth="1.25" />
        <circle cx="12.5" cy="12" r="1.75" stroke="currentColor" strokeWidth="1.25" />
        <path d="M5.25 7.25L10.75 4.75M5.25 8.75L10.75 11.25" stroke="currentColor" strokeWidth="1.25" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    route: 'documents',
    label: 'Documents',
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
        <path d="M4.5 2.5H9.5L12.5 5.5V13.5C12.5 13.7761 12.2761 14 12 14H4.5C4.22386 14 4 13.7761 4 13.5V3C4 2.72386 4.22386 2.5 4.5 2.5Z" stroke="currentColor" strokeWidth="1.25" strokeLinejoin="round" />
        <path d="M9.5 2.5V5.5H12.5" stroke="currentColor" strokeWidth="1.25" strokeLinejoin="round" />
        <path d="M6 8H10.5M6 10.5H10.5" stroke="currentColor" strokeWidth="1.25" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    route: 'executions',
    label: 'Executions',
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
        <circle cx="8" cy="8" r="5.75" stroke="currentColor" strokeWidth="1.25" />
        <path d="M8 5.5V8.25L10 9.75" stroke="currentColor" strokeWidth="1.25" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    ),
  },
  {
    route: 'settings',
    label: 'Settings',
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
        <circle cx="8" cy="8" r="2" stroke="currentColor" strokeWidth="1.25" />
        <path d="M8 1.5V3M8 13V14.5M14.5 8H13M3 8H1.5M12.5962 3.40381L11.5355 4.46447M4.46447 11.5355L3.40381 12.5962M12.5962 12.5962L11.5355 11.5355M4.46447 4.46447L3.40381 3.40381" stroke="currentColor" strokeWidth="1.25" strokeLinecap="round" />
      </svg>
    ),
  },
];

function getInitials(name: string): string {
  return name
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? '')
    .join('');
}

export function Sidebar({ activeRoute, onNavigate, user = DEFAULT_USER, theme, onToggleTheme }: SidebarProps) {
  const createWorkflow = useWorkflowStore((state) => state.createWorkflow);
  const setActiveWorkflow = useWorkflowStore((state) => state.setActiveWorkflow);
  const resetFlow = useFlowStore((state) => state.resetFlow);

  const handleNewWorkflow = () => {
    resetFlow();
    createWorkflow();
    onNavigate('workflows');
  };

  const handleNavigation = (route: AppRoute) => {
    if (route === 'workflows') {
      setActiveWorkflow(null);
    }
    onNavigate(route);
  };

  return (
    <aside className={styles.sidebar} aria-label="Main navigation">
      {/* Logo */}
      <div className={styles.header}>
        <div className={styles.brand}>
          <div className={styles.logoMark} aria-hidden="true">
            <svg width="18" height="18" viewBox="0 0 16 16" fill="none">
              <path d="M3 4.5H10.5M3 8H8M3 11.5H10.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
              <path d="M11.5 6.5L13.5 8L11.5 9.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </div>
          <div className={styles.brandCopy}>
            <span className={styles.logoText}>FlowDocs</span>
            <small>Document workspace</small>
          </div>
        </div>
        <button
          type="button"
          className={styles.themeToggle}
          onClick={onToggleTheme}
          title={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`}
          aria-label={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`}
        >
          {theme === 'light' ? '☀' : '◐'}
        </button>
      </div>

      {/* New Workflow CTA */}
      <button type="button" className={styles.newWorkflowBtn} onClick={handleNewWorkflow}>
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
          <path d="M7 2.5V11.5M2.5 7H11.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        </svg>
        New Workflow
      </button>

      {/* Navigation */}
      <nav className={styles.nav} aria-label="App sections">
        {NAV_ITEMS.map((item) => {
          const isActive = activeRoute === item.route;
          return (
            <button
              key={item.route}
              type="button"
              className={`${styles.navItem} ${isActive ? styles.navItemActive : ''}`}
              onClick={() => handleNavigation(item.route)}
              aria-current={isActive ? 'page' : undefined}
            >
              <span className={styles.navIcon}>{item.icon}</span>
              {item.label}
              {isActive && <span className={styles.activeIndicator}></span>}
            </button>
          );
        })}
      </nav>

      {/* User Footer */}
      <div className={styles.footer}>
        <div className={styles.avatar} aria-hidden="true">
          {user.avatarUrl ? (
            <img src={user.avatarUrl} alt="" className={styles.avatarImage} />
          ) : (
            getInitials(user.name)
          )}
        </div>
        <div className={styles.userInfo}>
          <span className={styles.userName}>{user.name}</span>
          <span className={styles.userRole}>Workspace Admin</span>
        </div>
        <button className={styles.chevronBtn}>
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
            <path d="M3 5l3 3 3-3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
        </button>
      </div>
    </aside>
  );
}
