// Copyright 2026 Justin Cook
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

import { Layout } from './components/Layout'
import { VoiceClient } from './components/VoiceClient'
import { ConfigEditor } from './components/ConfigEditor'
import { PromptStudio } from './components/PromptStudio'
import { ActivityLog } from './components/ActivityLog'
import { GovernanceDesk } from './components/GovernanceDesk'
import { Dashboard } from './components/Dashboard'
import { Kanban } from './components/Kanban'
import { useViewStore } from './store/viewStore'

function App() {
  const { activeView } = useViewStore()

  const renderView = () => {
    switch (activeView) {
      case 'dashboard':
        return <Dashboard />
      case 'kanban':
        return <Kanban />
      case 'voice':
        return <VoiceClient />
      case 'config':
        return <ConfigEditor />
      case 'prompts':
        return <PromptStudio />
      case 'logs':
        return <ActivityLog />
      case 'governance':
        return <GovernanceDesk />
      default:
        return <Dashboard />
    }
  }

  return <Layout>{renderView()}</Layout>
}

export default App
