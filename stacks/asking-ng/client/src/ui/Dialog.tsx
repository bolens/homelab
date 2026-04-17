import { type ReactNode, useEffect, useRef } from 'react';
import Button from './Button';
import { cx } from './cx';

type DialogOwnProps = {
  open: boolean;
  onClose: () => void;
  titleId: string;
  title: ReactNode;
  closeAriaLabel: string;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
};

export type DialogProps = DialogOwnProps &
  Omit<
    React.DialogHTMLAttributes<HTMLDialogElement>,
    keyof DialogOwnProps | 'aria-labelledby' | 'aria-modal' | 'ref'
  >;

export default function Dialog({
  open,
  onClose,
  titleId,
  title,
  closeAriaLabel,
  children,
  className,
  bodyClassName,
  ...rest
}: DialogProps) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (open) {
      if (!el.open) void el.showModal();
    } else if (el.open) {
      el.close();
    }
  }, [open]);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const handleClose = () => {
      onClose();
    };
    el.addEventListener('close', handleClose);
    return () => {
      el.removeEventListener('close', handleClose);
    };
  }, [onClose]);

  return (
    <dialog
      {...rest}
      ref={ref}
      className={cx('ui-dialog', className)}
      aria-labelledby={titleId}
      aria-modal='true'
    >
      <div className='ui-dialog__shell'>
        <header className='ui-dialog__header'>
          <h2 id={titleId} className='ui-dialog__title'>
            {title}
          </h2>
          <Button
            type='button'
            variant='ghost'
            size='sm'
            className='ui-dialog__close'
            aria-label={closeAriaLabel}
            onClick={onClose}
          >
            <span aria-hidden>×</span>
          </Button>
        </header>
        <div className={cx('ui-dialog__body', bodyClassName)}>{children}</div>
      </div>
    </dialog>
  );
}
