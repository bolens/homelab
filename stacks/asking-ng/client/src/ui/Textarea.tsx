import React from 'react';
import { cx } from './cx';

type TextareaProps = React.TextareaHTMLAttributes<HTMLTextAreaElement>;

const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(function Textarea(
  { className, ...props },
  ref,
) {
  return <textarea ref={ref} className={cx('ui-input', 'ui-textarea', className)} {...props} />;
});

export default Textarea;
