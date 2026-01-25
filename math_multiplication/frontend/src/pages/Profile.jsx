import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../AuthContext'
import '../App.css'

function Profile() {
  const { authLoading, user, profile, profileLoading, profileError, refreshProfile, updateDisplayName } =
    useAuth()
  const [displayName, setDisplayName] = useState('')
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState(null)
  const [saveSuccess, setSaveSuccess] = useState(null)

  useEffect(() => {
    if (profile?.display_name) {
      setDisplayName(profile.display_name)
    }
  }, [profile?.display_name])

  useEffect(() => {
    if (!authLoading && user) {
      refreshProfile()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authLoading, user])

  const handleSave = async () => {
    try {
      setSaving(true)
      setSaveError(null)
      setSaveSuccess(null)

      const trimmed = displayName.trim()
      if (!trimmed) {
        setSaveError('Display name cannot be empty')
        return
      }
      if (trimmed.length > 32) {
        setSaveError('Display name must be 32 characters or less')
        return
      }

      await updateDisplayName(trimmed)
      setSaveSuccess('Saved')
    } catch (e) {
      setSaveError(e?.message || String(e))
    } finally {
      setSaving(false)
    }
  }

  if (authLoading) {
    return (
      <div className="container">
        <div className="game-container">Loading...</div>
      </div>
    )
  }

  if (!user) {
    return (
      <div className="container">
        <div className="game-container">
          <h2>Profile</h2>
          <div>Please sign in to edit your profile.</div>
          <div style={{ marginTop: 12 }}>
            <Link className="nav-link" to="/game">
              Go to Game
            </Link>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="container">
      <div className="game-container">
        <h2>Profile</h2>

        {profileError && <div className="error">Error: {profileError}</div>}

        <div style={{ width: '100%', maxWidth: 420 }}>
          <div style={{ marginBottom: 8, color: '#333', fontWeight: 600 }}>Display name</div>
          <input
            type="text"
            className="name-input"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            placeholder="Your display name"
            disabled={profileLoading || saving}
          />
          <div style={{ marginTop: 8, fontSize: '0.9rem', color: '#666' }}>
            This is what shows on the leaderboard. Please avoid full names.
          </div>

          <div style={{ marginTop: 16, display: 'flex', gap: 12, alignItems: 'center' }}>
            <button className="start-button" type="button" onClick={handleSave} disabled={saving}>
              {saving ? 'Saving…' : 'Save'}
            </button>
            <Link className="nav-link" to="/game">
              Back
            </Link>
          </div>

          {saveError && (
            <div className="error" style={{ marginTop: 12 }}>
              Error: {saveError}
            </div>
          )}
          {saveSuccess && <div style={{ marginTop: 12, color: '#388E3C' }}>{saveSuccess}</div>}
        </div>
      </div>
    </div>
  )
}

export default Profile

