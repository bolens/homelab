import { useCallback, useEffect, useRef, useState } from 'react';
import Button from '../ui/Button';
import { cx } from '../ui/cx';
import { IconCheck, IconCopy } from './icons/UiIcons';

const COPY_FLASH_MS = 2000;

type Props = {
  /** Return `true` when text was written to the clipboard successfully. */
  onCopy: () => Promise<boolean>;
  children: React.ReactNode;
  className?: string;
  disabled?: boolean;
};

/**
 * Secondary-style control: shows a checkmark briefly after a successful clipboard copy.
 * Keep full text in `children` for tooltips and screen readers; icons are decorative.
 */
export default function CopyFeedbackButton({ onCopy, children, className, disabled }: Props) {
  const [copied, setCopied] = useState(false);
  const clearRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (clearRef.current) clearTimeout(clearRef.current);
    };
  }, []);

  const handleClick = useCallback(async () => {
    if (disabled) return;
    if (clearRef.current) {
      clearTimeout(clearRef.current);
      clearRef.current = null;
    }
    const ok = await onCopy();
    if (!ok) return;
    setCopied(true);
    clearRef.current = setTimeout(() => {
      setCopied(false);
      clearRef.current = null;
    }, COPY_FLASH_MS);
  }, [disabled, onCopy]);

  return (
    <Button
      type='button'
      variant='secondary'
      className={cx('ui-button--with-inline-icon', className)}
      disabled={disabled}
      onClick={() => void handleClick()}
    >
      {copied ? (
        <IconCheck className='ui-button__icon' aria-hidden />
      ) : (
        <IconCopy className='ui-button__icon' aria-hidden />
      )}
      {children}
    </Button>
  );
}
