import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ConnectAccounts } from '../../components/ConnectAccounts'
import { PortfolioUpload } from '../../components/PortfolioUpload'
import { SettingsForm } from '../../components/SettingsForm'

export function Onboarding() {
  const [saved, setSaved] = useState(false)
  return (
    <div className="page">
      <h1>Welcome to GigBid</h1>
      <p className="muted">Set up your profile in a few minutes. You can change everything later in Settings.</p>
      <div className="stack">
        <SettingsForm mode="onboarding" onSaved={() => setSaved(true)} />
        {saved && (
          <p className="note" role="status">
            Your settings are saved. <Link to="/">Go to your job inbox</Link>
          </p>
        )}
        <ConnectAccounts />
        <PortfolioUpload />
      </div>
    </div>
  )
}
