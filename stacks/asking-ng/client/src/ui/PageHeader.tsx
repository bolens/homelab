import React from 'react';
import { cx } from './cx';

type PageHeaderProps = React.HTMLAttributes<HTMLElement> & {
  title: React.ReactNode;
  /** Optional stable id for the primary `<h1>` (landmarks, skip links, tests). */
  titleId?: string;
  subtitle?: React.ReactNode;
  titleClassName?: string;
  subtitleClassName?: string;
  actions?: React.ReactNode;
};

export default function PageHeader({
  title,
  titleId,
  subtitle,
  actions,
  className,
  titleClassName,
  subtitleClassName,
  children,
  ...props
}: PageHeaderProps) {
  return (
    <header className={cx('ui-page-header', className)} {...props}>
      <h1 id={titleId} className={cx('ui-page-header__title', titleClassName)}>
        {title}
      </h1>
      {subtitle ? <p className={cx('ui-page-header__subtitle', subtitleClassName)}>{subtitle}</p> : null}
      {actions ? <div className='ui-page-header__actions'>{actions}</div> : null}
      {children}
    </header>
  );
}
