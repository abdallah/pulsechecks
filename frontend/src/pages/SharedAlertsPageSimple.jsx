import Layout from '../components/Layout'

export default function SharedAlertsPageSimple({ user, onLogout }) {
  console.log('SharedAlertsPageSimple component loaded')
  
  return (
    <Layout user={user} onLogout={onLogout}>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <h1>Shared Alert Channels - SIMPLE TEST</h1>
        <p>This is a simple test to see if the component can render at all.</p>
      </div>
    </Layout>
  )
}
