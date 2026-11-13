import { ConnectAccounts } from '../../components/ConnectAccounts'
import { MemoryViewer } from '../../components/MemoryViewer'
import { PortfolioUpload } from '../../components/PortfolioUpload'
import { SettingsForm } from '../../components/SettingsForm'

export function Settings() {
  return (
    <div className="page">
      <h1>Settings</h1>
      <div className="stack">
        <SettingsForm mode="settings" />
        <ConnectAccounts />
        <PortfolioUpload />
        <MemoryViewer />
      </div>
    </div>
  )
}
