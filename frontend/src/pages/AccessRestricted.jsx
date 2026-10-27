import { Link, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { ShieldAlert, ArrowLeft } from 'lucide-react'
import { useAppState } from '@/state/AppState'

export default function AccessRestricted() {
  const { currentUser } = useAppState()
  const navigate = useNavigate()
  
  const getDashboardPath = () => {
    if (!currentUser) return '/login'
    return currentUser.id === 'admin' ? '/admin' : `/${currentUser.id}`
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-base/80 backdrop-blur-md p-4 font-sans text-ink">
      <motion.div 
        initial={{ opacity: 0, scale: 0.9, y: 20 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        transition={{ type: "spring", bounce: 0.4, duration: 0.6 }}
        className="w-full max-w-md rounded-2xl border border-danger/20 bg-surface p-8 text-center shadow-[0_20px_50px_rgba(239,68,68,0.15)] relative overflow-hidden"
      >
        <div className="absolute top-0 left-0 w-full h-1 bg-danger" />
        <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-danger/10 text-danger mb-6">
          <ShieldAlert size={32} />
        </div>
        <h1 className="text-xl tracking-tight font-bold uppercase text-ink mb-2">Access Restricted</h1>
        <p className="text-sm text-muted mb-8">
          You do not have permission to view this department's dashboard. Your current role is <span className="font-bold text-ink uppercase">{currentUser?.id || 'Unknown'}</span>.
        </p>
        
        <button 
          onClick={() => navigate(getDashboardPath())}
          className="btn-primary w-full py-3 text-sm font-bold flex items-center justify-center gap-2"
        >
          <ArrowLeft size={16} />
          RETURN TO MY DASHBOARD
        </button>
      </motion.div>
    </div>
  )
}
