import React from 'react';
import { cx } from './cx';

type SectionPanelProps = Omit<React.HTMLAttributes<HTMLElement>, 'title'> & {
  title: React.ReactNode;
  titleId: string;
  hint?: React.ReactNode;
  headerClassName?: string;
  bodyClassName?: string;
};

export default function SectionPanel({
  title,
  titleId,
  hint,
  className,
  headerClassName,
  bodyClassName,
  children,
  ...props
}: SectionPanelProps) {
  return (
    <section className={cx('ui-section-panel', className)} aria-labelledby={titleId} {...props}>
      <div className={cx('ui-section-panel__header', headerClassName)}>
        <h2 id={titleId} className='ui-section-panel__title'>
          {title}
        </h2>
        {hint ? <p className='ui-section-panel__hint'>{hint}</p> : null}
      </div>
      <div className={cx('ui-section-panel__body', bodyClassName)}>{children}</div>
    </section>
  );
}
