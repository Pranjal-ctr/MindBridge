import { Hammer } from 'lucide-react';
import { EmptyState } from '../widgets/EmptyState';
import { PageHeader } from '../widgets/PageHeader';

/** Temporary stub rendered while a module's real page is being built. */
export function UnderConstruction({ title, description }: { title: string; description?: string }) {
  return (
    <>
      <PageHeader title={title} description={description} />
      <EmptyState
        icon={Hammer}
        title="This module is on its way"
        description="It's part of the current build and will appear here shortly."
      />
    </>
  );
}
