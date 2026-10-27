import { useEffect, useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import { ArrowUpDown, Search } from 'lucide-react'
import PageHeader from '@/components/app/PageHeader'
import StageFooter from '@/components/app/StageFooter'
import DeptTag from '@/components/common/DeptTag'
import ScoreMeter from '@/components/common/ScoreMeter'
import TaskDetail from '@/components/tasks/TaskDetail'
import ExplainDrawer from '@/components/optimize/ExplainDrawer'
import { tasks } from '@/data/tasks'
import { corridors } from '@/data/corridors'
import { DEPT_LIST } from '@/lib/constants'
import { duration } from '@/lib/format'

const corridorName = (id) => corridors.find((c) => c.id === id)?.name ?? id

const rowVariants = {
  hidden: { opacity: 0, x: -10 },
  visible: (i) => ({
    opacity: 1,
    x: 0,
    transition: {
      delay: 0.03 * i,
      duration: 0.35,
      ease: [0.16, 1, 0.3, 1],
    },
  }),
}

export default function Tasks() {
  const [dept, setDept] = useState(null)
  const [query, setQuery] = useState('')
  const [sort, setSort] = useState('score')
  const [selected, setSelected] = useState(null)
  const [explainId, setExplainId] = useState(null)

  useEffect(() => {
    document.title = 'Pending work — RailOpt'
  }, [])

  const rows = useMemo(() => {
    let list = tasks
    if (dept) list = list.filter((t) => t.department === dept)
    if (query.trim()) {
      const q = query.toLowerCase()
      list = list.filter(
        (t) =>
          t.id.toLowerCase().includes(q) ||
          t.defectType.toLowerCase().includes(q) ||
          t.section.toLowerCase().includes(q) ||
          corridorName(t.corridorId).toLowerCase().includes(q)
      )
    }
    return [...list].sort((a, b) =>
      sort === 'score' ? b.score - a.score : b.daysOverdue - a.daysOverdue
    )
  }, [dept, query, sort])

  const breaching = rows.filter((t) => t.slaDays <= 0).length

  return (
    <>
      <PageHeader
        title="Pending work, all three departments"
        description="Every open task on one urgency scale. Open any row to see exactly which factors raised or lowered its score."
      />

      <div className="px-5 py-6 sm:px-8">
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
          className="flex flex-wrap items-center gap-3"
        >
          <div className="relative">
            <Search
              size={15}
              className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-faint"
            />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search defect, ID or section"
              className="w-[250px] rounded-panel border border-line bg-surface py-2 pl-9 pr-3 text-[13.5px] placeholder:text-faint transition-all duration-200 focus:border-merge/50 focus:shadow-[0_0_0_3px_rgb(var(--c-merge)/0.08)] focus:outline-none"
            />
          </div>

          <div className="flex flex-wrap gap-1.5">
            <button
              onClick={() => setDept(null)}
              className={`rounded-panel border px-3 py-1.5 text-[13px] transition-all duration-200 ${
                dept === null ? 'border-merge/50 bg-raised text-ink shadow-sm' : 'border-line text-muted hover:text-ink'
              }`}
            >
              All
            </button>
            {DEPT_LIST.map((d) => (
              <button
                key={d.id}
                onClick={() => setDept(dept === d.id ? null : d.id)}
                className={`flex items-center gap-2 rounded-panel border px-3 py-1.5 text-[13px] transition-all duration-200 ${
                  dept === d.id ? 'border-merge/50 bg-raised text-ink shadow-sm' : 'border-line text-muted hover:text-ink'
                }`}
              >
                <span className="h-1.5 w-1.5 rounded-full" style={{ background: d.color }} />
                {d.name}
              </button>
            ))}
          </div>

          <button
            onClick={() => setSort(sort === 'score' ? 'overdue' : 'score')}
            className="ml-auto flex items-center gap-2 rounded-panel border border-line px-3 py-1.5 text-[13px] text-muted transition-all duration-200 hover:text-ink hover:shadow-sm"
          >
            <ArrowUpDown size={13} />
            {sort === 'score' ? 'By urgency' : 'By days overdue'}
          </button>
        </motion.div>

        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.2, duration: 0.4 }}
          className="mt-4 text-[13px] text-muted"
        >
          {rows.length} tasks
          {breaching > 0 && (
            <>
              {' · '}
              <span className="text-danger">{breaching} past their deferral limit</span>
            </>
          )}
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15, duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
          className="mt-3 overflow-hidden rounded-panel border border-line"
        >
          <table className="w-full text-left">
            <thead>
              <tr className="border-b border-line bg-surface">
                <th className="px-4 py-3 text-[12px] font-normal text-faint">Defect</th>
                <th className="hidden px-4 py-3 text-[12px] font-normal text-faint md:table-cell">
                  Department
                </th>
                <th className="hidden px-4 py-3 text-[12px] font-normal text-faint lg:table-cell">
                  Section
                </th>
                <th className="hidden px-4 py-3 text-[12px] font-normal text-faint sm:table-cell">
                  Overdue
                </th>
                <th className="hidden px-4 py-3 text-[12px] font-normal text-faint lg:table-cell">
                  Duration
                </th>
                <th className="px-4 py-3 text-[12px] font-normal text-faint">Urgency</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((t, idx) => (
                <motion.tr
                  key={t.id}
                  custom={idx}
                  variants={rowVariants}
                  initial="hidden"
                  animate="visible"
                  onClick={() => setSelected(t)}
                  tabIndex={0}
                  onKeyDown={(e) => e.key === 'Enter' && setSelected(t)}
                  className="cursor-pointer border-b border-hair/60 bg-surface/50 transition-all duration-200 last:border-0 hover:bg-raised/40"
                >
                  <td className="px-4 py-3.5">
                    <p className="text-[14px] leading-snug">{t.defectType}</p>
                    <p className="mt-0.5 font-mono text-[11.5px] text-faint">{t.id}</p>
                  </td>
                  <td className="hidden px-4 py-3.5 md:table-cell">
                    <DeptTag dept={t.department} size="sm" />
                  </td>
                  <td className="hidden px-4 py-3.5 lg:table-cell">
                    <p className="font-mono text-[12.5px]">{t.section}</p>
                    <p className="mt-0.5 text-[11.5px] text-faint">{corridorName(t.corridorId)}</p>
                  </td>
                  <td className="hidden px-4 py-3.5 sm:table-cell">
                    <span
                      className={`font-mono tnum text-[13px] ${
                        t.slaDays <= 0 ? 'text-danger' : 'text-muted'
                      }`}
                    >
                      {t.daysOverdue}d
                    </span>
                  </td>
                  <td className="hidden px-4 py-3.5 font-mono text-[12.5px] text-muted lg:table-cell">
                    {duration(t.estDuration)}
                  </td>
                  <td className="px-4 py-3.5">
                    <ScoreMeter score={t.score} width={58} />
                  </td>
                </motion.tr>
              ))}
            </tbody>
          </table>

          {rows.length === 0 && (
            <div className="px-6 py-14 text-center">
              <p className="text-[14px] text-muted">No task matches that search.</p>
              <button
                onClick={() => {
                  setQuery('')
                  setDept(null)
                }}
                className="mt-2 rounded-panel text-[13.5px] text-merge hover:text-ink transition-colors"
              >
                Clear the filters
              </button>
            </div>
          )}
        </motion.div>
      </div>

      <TaskDetail
        task={selected}
        onClose={() => setSelected(null)}
        onExplain={(id) => {
          setSelected(null)
          setExplainId(id)
        }}
      />
      <ExplainDrawer taskId={explainId} onClose={() => setExplainId(null)} />
      <StageFooter reason="see where this work landed in the schedule" />
    </>
  )
}
