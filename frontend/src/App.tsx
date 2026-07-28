import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { ConfigProvider } from 'antd';
import ProjectList from './pages/ProjectList';
import ProjectWorkshop from './pages/project/ProjectWorkshop';
import WorldviewPage from './pages/project/WorldviewPage';
import CharactersPage from './pages/project/CharactersPage';
import OutlinePage from './pages/project/OutlinePage';
import WritingPage from './pages/project/WritingPage';
import VersionHistoryPage from './pages/project/VersionHistory';
import ForeshadowingPage from './pages/project/ForeshadowingPage';
import ConsistencyPage from './pages/project/ConsistencyPage';
import EventsPage from './pages/project/EventsPage';
import StoryCorePage from './pages/project/StoryCorePage';
import KnowledgePage from './pages/project/KnowledgePage';
import PromptTemplatePage from './pages/project/PromptTemplatePage';
import DebtDashboard from './pages/project/DebtDashboard';
import ContractsPage from './pages/project/ContractsPage';
import ReaderPage from './pages/project/ReaderPage';
import SearchPage from './pages/project/SearchPage';
import CreativePage from './pages/project/CreativePage';
import StylePage from './pages/project/StylePage';
import ContextAgentView from './pages/project/ContextAgentView';
import DeconstructionPage from './pages/project/DeconstructionPage';
import InitWizardPage from './pages/project/InitWizardPage';
import AnalysisPage from './pages/project/AnalysisPage';
import RelationshipPage from './pages/project/RelationshipPage';
import ProjectSettingsPage from './pages/project/ProjectSettingsPage';
import SkillsPage from './pages/project/SkillsPage';
import SettingsPage from './pages/SettingsPage';
import AppLayout from './components/layout/AppLayout';
import './App.css';

function ProjectLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}

function App() {
  return (
    <ConfigProvider
      theme={{
        token: {
          colorPrimary: '#5B9BD5',
          borderRadius: 8,
          colorBgContainer: '#FFFFFF',
          colorBgLayout: '#FAFAFA',
          colorBorderSecondary: '#f0f0f0',
        },
      }}
    >
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<ProjectList />} />
          <Route path="/creative" element={<CreativePage />} />
          <Route path="/style" element={<StylePage />} />
          <Route path="/deconstruction" element={<DeconstructionPage />} />
          <Route path="/projects/:id" element={<ProjectWorkshop />} />
          <Route path="/projects/:id/workshop" element={<ProjectWorkshop />} />
          <Route path="/projects/:id/worldview" element={<WorldviewPage />} />
          <Route path="/projects/:id/characters" element={<CharactersPage />} />
          <Route path="/projects/:id/outline" element={<OutlinePage />} />
          <Route path="/projects/:id/writing" element={<WritingPage />} />
          <Route path="/projects/:id/versions" element={<VersionHistoryPage />} />
          <Route path="/projects/:id/foreshadowing" element={<ForeshadowingPage />} />
          <Route path="/projects/:id/story-core" element={<StoryCorePage />} />
          <Route path="/projects/:id/consistency" element={<ConsistencyPage />} />
          <Route path="/projects/:id/events" element={<EventsPage />} />
          <Route path="/projects/:id/knowledge" element={<KnowledgePage />} />
          <Route path="/projects/:id/prompt-templates" element={<PromptTemplatePage />} />
          <Route path="/projects/:id/reader" element={<ReaderPage />} />
          <Route path="/projects/search" element={<SearchPage />} />
          <Route path="/projects/:id/search" element={<SearchPage />} />
          <Route path="/projects/:id/debt" element={<DebtDashboard />} />
          <Route path="/projects/:id/contracts" element={<ContractsPage />} />
          <Route path="/projects/:id/settings" element={<ProjectSettingsPage />} />
          <Route path="/projects/:id/creative" element={<CreativePage />} />
          <Route path="/projects/:id/style" element={<StylePage />} />
          <Route path="/projects/:id/task-book" element={<ContextAgentView />} />
          <Route path="/projects/:id/deconstruction" element={<DeconstructionPage />} />
          <Route path="/projects/:id/relationships" element={<RelationshipPage />} />
          <Route path="/projects/:id/skills" element={<SkillsPage />} />
          <Route path="/projects/:id/analysis" element={<AnalysisPage />} />
          <Route path="/projects/new" element={<InitWizardPage />} />
          <Route path="/projects/:id/init-wizard" element={<InitWizardPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Routes>
      </BrowserRouter>
    </ConfigProvider>
  );
}

export default App;