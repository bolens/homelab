import type { SVGProps } from 'react';

const stroke = {
  fill: 'none' as const,
  stroke: 'currentColor',
  strokeWidth: 2,
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
};

type IconProps = SVGProps<SVGSVGElement> & { title?: string };

function baseProps(className: string | undefined, props: IconProps) {
  const { title, children, ...rest } = props;
  return {
    ...rest,
    className: ['ui-icon', className].filter(Boolean).join(' '),
    viewBox: '0 0 24 24' as const,
    xmlns: 'http://www.w3.org/2000/svg' as const,
    'aria-hidden': title ? undefined : true,
    role: title ? ('img' as const) : undefined,
    'aria-label': title,
    children: title ? (
      <>
        <title>{title}</title>
        {children}
      </>
    ) : (
      children
    ),
  };
}

/** Clipboard — pair with visible button text or parent `aria-label`. */
export function IconCopy(props: IconProps) {
  const p = baseProps(props.className, props);
  return (
    <svg {...p} width={props.width ?? 16} height={props.height ?? 16}>
      <rect x={9} y={9} width={13} height={13} rx={2} {...stroke} />
      <path d='M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1' {...stroke} />
    </svg>
  );
}

export function IconCheck(props: IconProps) {
  const p = baseProps(props.className, props);
  return (
    <svg {...p} width={props.width ?? 16} height={props.height ?? 16}>
      <path d='M20 6 9 17l-5-5' {...stroke} />
    </svg>
  );
}

/** Share / export upward (system share sheet). */
export function IconShare(props: IconProps) {
  const p = baseProps(props.className, props);
  return (
    <svg {...p} width={props.width ?? 16} height={props.height ?? 16}>
      <path d='M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8' {...stroke} />
      <path d='m16 6-4-4-4 4M12 2v13' {...stroke} />
    </svg>
  );
}

export function IconWifiOff(props: IconProps) {
  const p = baseProps(props.className, props);
  return (
    <svg {...p} width={props.width ?? 18} height={props.height ?? 18}>
      <path d='m2 2 20 20' {...stroke} />
      <path d='M8.5 16.5a5 5 0 0 1 7 0' {...stroke} />
      <path d='M5 12.55a10 10 0 0 1 5.17-2.39' {...stroke} />
      <path d='M19 12.55a10 10 0 0 0-.91-.45' {...stroke} />
      <path d='M2 8.82a15 15 0 0 1 5.11-2.95' {...stroke} />
      <path d='M22 8.82a15 15 0 0 0-3.28-2.15' {...stroke} />
      <path d='M10.62 5.17A13 13 0 0 1 20.38 8' {...stroke} />
      <path d='M12 20h.01' {...stroke} />
    </svg>
  );
}

export function IconListPolls(props: IconProps) {
  const p = baseProps(props.className, props);
  return (
    <svg {...p} width={props.width ?? 20} height={props.height ?? 20}>
      <path d='M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01' {...stroke} />
    </svg>
  );
}

export function IconSignOut(props: IconProps) {
  const p = baseProps(props.className, props);
  return (
    <svg {...p} width={props.width ?? 20} height={props.height ?? 20}>
      <path d='M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4' {...stroke} />
      <path d='M16 17l5-5-5-5M21 12H9' {...stroke} />
    </svg>
  );
}

export function IconLayoutDashboard(props: IconProps) {
  const p = baseProps(props.className, props);
  return (
    <svg {...p} width={16} height={16}>
      <rect x={3} y={3} width={7} height={9} rx={1} {...stroke} />
      <rect x={14} y={3} width={7} height={5} rx={1} {...stroke} />
      <rect x={14} y={12} width={7} height={9} rx={1} {...stroke} />
      <rect x={3} y={16} width={7} height={5} rx={1} {...stroke} />
    </svg>
  );
}

export function IconUsers(props: IconProps) {
  const p = baseProps(props.className, props);
  return (
    <svg {...p} width={16} height={16}>
      <path d='M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2' {...stroke} />
      <circle cx={9} cy={7} r={4} {...stroke} />
      <path d='M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75' {...stroke} />
    </svg>
  );
}

export function IconBarChart(props: IconProps) {
  const p = baseProps(props.className, props);
  return (
    <svg {...p} width={16} height={16}>
      <path d='M3 3v18h18' {...stroke} />
      <path d='M7 16v-5M12 16V8M17 16v-3' {...stroke} />
    </svg>
  );
}

export function IconFileText(props: IconProps) {
  const p = baseProps(props.className, props);
  return (
    <svg {...p} width={16} height={16}>
      <path d='M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z' {...stroke} />
      <path d='M14 2v4h4' {...stroke} />
      <path d='M10 9H8M16 13H8M16 17H8M10 13H8' {...stroke} />
    </svg>
  );
}

export function IconDownload(props: IconProps) {
  const p = baseProps(props.className, props);
  return (
    <svg {...p} width={16} height={16}>
      <path d='M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4' {...stroke} />
      <path d='m7 10 5 5 5-5M12 15V3' {...stroke} />
    </svg>
  );
}

export function IconActivity(props: IconProps) {
  const p = baseProps(props.className, props);
  return (
    <svg {...p} width={16} height={16}>
      <path d='M22 12h-4l-3 9L9 3 6 12H2' {...stroke} />
    </svg>
  );
}

/** “View as” / impersonation — distinct from {@link IconUsers}. */
export function IconCircleUser(props: IconProps) {
  const p = baseProps(props.className, props);
  return (
    <svg {...p} width={16} height={16}>
      <circle cx={12} cy={12} r={10} {...stroke} />
      <circle cx={12} cy={10} r={3} {...stroke} />
      <path d='M7 20.5a5 5 0 0 1 10 0' {...stroke} />
    </svg>
  );
}

export function IconHouse(props: IconProps) {
  const p = baseProps(props.className, props);
  return (
    <svg {...p} width={16} height={16}>
      <path d='m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z' {...stroke} />
      <path d='M9 22V12h6v10' {...stroke} />
    </svg>
  );
}

export function IconLogOut(props: IconProps) {
  const p = baseProps(props.className, props);
  return (
    <svg {...p} width={16} height={16}>
      <path d='M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4' {...stroke} />
      <path d='M16 17l5-5-5-5M21 12H9' {...stroke} />
    </svg>
  );
}

export function IconTrash2(props: IconProps) {
  const p = baseProps(props.className, props);
  return (
    <svg {...p} width={16} height={16}>
      <path
        d='M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2m3 0v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6h14ZM10 11v6M14 11v6'
        {...stroke}
      />
    </svg>
  );
}
