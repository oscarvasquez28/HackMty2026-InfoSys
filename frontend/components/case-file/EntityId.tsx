"use client";

// Task 3 (heading): renders one prefixed entity id (RFC:... / EMP:...) with its resolved display
// name when the run supplied one, and flags a missing or unrecognized prefix inline.

import React from "react";
import type { EntityRef } from "@/lib/caseFile/derive";

interface EntityIdProps {
  entity: EntityRef;
}

export const EntityId: React.FC<EntityIdProps> = ({ entity }) => {
  const hasPrefix = entity.id.includes(":");
  const unknownPrefix = hasPrefix && entity.prefix !== "RFC" && entity.prefix !== "EMP";

  return (
    <span className="inline-flex flex-wrap items-baseline gap-x-2">
      <span data-entity-id={entity.id} className="font-mono text-sm font-bold text-paper-ink">
        {entity.id}
      </span>
      {entity.name && <span className="font-serif text-base">{entity.name}</span>}
      {entity.kindLabel && <span className="text-[11px] text-paper-muted">{entity.kindLabel}</span>}
      {!hasPrefix && (
        <span className="rounded-sm bg-evidence-proven-soft px-1.5 text-[11px] font-semibold text-evidence-proven">
          Missing id prefix
        </span>
      )}
      {hasPrefix && unknownPrefix && (
        <span className="rounded-sm bg-evidence-probable-soft px-1.5 text-[11px] font-semibold text-evidence-probable">
          Unknown id prefix
        </span>
      )}
    </span>
  );
};
