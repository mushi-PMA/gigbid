import { Navigate, Outlet, Route, Routes, useLocation } from 'react-router-dom'
import { DegradedBanner } from '../components/DegradedBanner'
import { Layout } from '../components/Layout'
import { Loading } from '../components/Loading'
import { useSession } from '../lib/session'
import { Analytics } from './analytics/Analytics'
import { Approvals } from './approvals/Approvals'
import { Inbox } from './inbox/Inbox'
import { JobDetail } from './jobs/[id]/JobDetail'
import { MessageThread } from './messages/MessageThread'
import { Messages } from './messages/Messages'
import { Onboarding } from './onboarding/Onboarding'
import { Pipeline } from './pipeline/Pipeline'
import { RunViewer } from './runs/[id]/RunViewer'
import { Settings } from './settings/Settings'
import { SignIn } from './sign-in/SignIn'
import { ProposalStudio } from './studio/[id]/ProposalStudio'

/** Sends signed-out users (and any 401 from the API) to the sign-in page. */
function RequireSession() {
  const { user, checking } = useSession()
  const location = useLocation()
  if (checking) return <Loading label="Checking your session" />
  if (!user) return <Navigate to="/sign-in" replace state={{ from: location.pathname }} />
  return <Outlet />
}

export function App() {
  return (
    <>
      <DegradedBanner />
      <Routes>
        <Route path="/sign-in" element={<SignIn />} />
        <Route element={<RequireSession />}>
          <Route element={<Layout />}>
            <Route path="/" element={<Inbox />} />
            <Route path="/onboarding" element={<Onboarding />} />
            <Route path="/jobs/:jobId" element={<JobDetail />} />
            <Route path="/approvals" element={<Approvals />} />
            <Route path="/studio/:threadId" element={<ProposalStudio />} />
            <Route path="/pipeline" element={<Pipeline />} />
            <Route path="/messages" element={<Messages />} />
            <Route path="/messages/:threadId" element={<MessageThread />} />
            <Route path="/runs/:threadId" element={<RunViewer />} />
            <Route path="/analytics" element={<Analytics />} />
            <Route path="/settings" element={<Settings />} />
          </Route>
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </>
  )
}
