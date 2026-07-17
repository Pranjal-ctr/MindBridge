import { useState, type ReactNode } from 'react';
import { Loader2 } from 'lucide-react';
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '../../ui/alert-dialog';
import { Button } from '../../ui/button';
import { Label } from '../../ui/label';
import { Textarea } from '../../ui/textarea';

interface ConfirmActionDialogProps {
  /** Element that opens the dialog. Omit to control externally via open/onOpenChange. */
  trigger?: ReactNode;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  title: string;
  description: ReactNode;
  confirmLabel?: string;
  /** Renders the confirm button in the destructive style. */
  destructive?: boolean;
  /** Require a typed reason before confirming (passed to onConfirm, min 10 chars). */
  requireReason?: boolean;
  reasonLabel?: string;
  reasonPlaceholder?: string;
  /** Runs on confirm; the dialog closes when the promise resolves. Throw to keep it open. */
  onConfirm: (reason?: string) => void | Promise<void>;
}

export function ConfirmActionDialog({
  trigger,
  open: controlledOpen,
  onOpenChange,
  title,
  description,
  confirmLabel = 'Confirm',
  destructive = false,
  requireReason = false,
  reasonLabel = 'Reason',
  reasonPlaceholder = 'Explain why (recorded in the audit log)…',
  onConfirm,
}: ConfirmActionDialogProps) {
  const [internalOpen, setInternalOpen] = useState(false);
  const [reason, setReason] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const open = controlledOpen ?? internalOpen;
  const setOpen = (next: boolean) => {
    if (!next) setReason('');
    setInternalOpen(next);
    onOpenChange?.(next);
  };

  const reasonInvalid = requireReason && reason.trim().length < 10;

  const handleConfirm = async () => {
    setSubmitting(true);
    try {
      await onConfirm(requireReason ? reason.trim() : undefined);
      setOpen(false);
    } catch {
      // Caller surfaces the error (toast); keep the dialog open for retry.
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AlertDialog open={open} onOpenChange={setOpen}>
      {trigger && <AlertDialogTrigger asChild>{trigger}</AlertDialogTrigger>}
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{title}</AlertDialogTitle>
          <AlertDialogDescription>{description}</AlertDialogDescription>
        </AlertDialogHeader>
        {requireReason && (
          <div className="grid gap-2">
            <Label htmlFor="confirm-reason">{reasonLabel}</Label>
            <Textarea
              id="confirm-reason"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder={reasonPlaceholder}
              rows={3}
            />
            <p className="text-xs text-muted-foreground">Minimum 10 characters.</p>
          </div>
        )}
        <AlertDialogFooter>
          <AlertDialogCancel disabled={submitting}>Cancel</AlertDialogCancel>
          <Button
            variant={destructive ? 'destructive' : 'default'}
            disabled={submitting || reasonInvalid}
            onClick={handleConfirm}
          >
            {submitting && <Loader2 className="h-4 w-4 animate-spin" />}
            {confirmLabel}
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
