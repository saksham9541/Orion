"""
Post-processing module for block merging analysis.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Set

from railopt.models import BlockPlan, MaintenanceTask, Department

@dataclass
class MergeReport:
    """Statistics on block merging."""
    total_merged_blocks: int = 0
    total_hours_saved: float = 0.0
    departments_coordinated_count: Dict[str, int] = field(default_factory=dict)
    merged_block_ids: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


class BlockMerger:
    """Analyzes and quantifies merge opportunities in block plans."""

    def analyze_merge_opportunities(
        self, plan: BlockPlan, tasks: List[MaintenanceTask]
    ) -> MergeReport:
        """
        Analyze a schedule to identify how much time was saved by merging
        multiple departments into single blocks.
        """
        report = MergeReport()
        task_map = {t.task_id: t for t in tasks}
        
        for block in plan.scheduled_blocks:
            if not block.task_ids:
                continue
                
            depts_present = set()
            for tid in block.task_ids:
                if tid in task_map:
                    depts_present.add(task_map[tid].department.value)
                    
            if len(depts_present) > 1:
                block.is_merged = True
                report.total_merged_blocks += 1
                report.merged_block_ids.append(block.block_id)
                
                # Calculate hours saved.
                # If these were done separately, they'd each need their own block time.
                # Simplified: we assume we saved (N-1) * block.duration_hours
                savings = (len(depts_present) - 1) * block.duration_hours
                block.merge_savings_hours = savings
                report.total_hours_saved += savings
                
                # Track coordination counts
                coord_key = "-".join(sorted(depts_present))
                report.departments_coordinated_count[coord_key] = (
                    report.departments_coordinated_count.get(coord_key, 0) + 1
                )
            else:
                block.is_merged = False
                block.merge_savings_hours = 0.0

        # Update the overall plan metrics
        plan.total_merge_savings_hours = report.total_hours_saved

        if report.total_merged_blocks > 0:
            report.recommendations.append(
                f"Successfully identified {report.total_merged_blocks} multi-department blocks, "
                f"saving approximately {report.total_hours_saved:.1f} hours of traffic disruption."
            )
        else:
            report.recommendations.append(
                "No merge opportunities found. Consider relaxing constraints or "
                "widening planning horizons to allow better cross-department alignment."
            )

        return report
