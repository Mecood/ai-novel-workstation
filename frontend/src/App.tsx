import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { ConfigProvider } from 'antd';
import ProjectList from './pages/ProjectList';
import ProjectWorkshop from './pages/project/ProjectWorkshop';
import WorldviewPage from './pages/project/WorldviewPage';
import CharactersPage from './pages/project/CharactersPage';
import OutlinePage from './pages/project/OutlinePage';
import WritingPage from './pages/project/WritingPage';
import ForeshadowingPage from './pages/project/ForeshadowingPage';
import ConsistencyPage from './pages/project/ConsistencyPage';
import KnowledgePage from './pages/project/KnowledgePage';
import ReaderPage from './pages/project/ReaderPage';
import ProjectSettingsPage from './pages/project/ProjectSettingsPage';
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
          <Route path="/projects/:id" element={<ProjectWorkshop />} />
          <Route path="/projects/:id/workshop" element={<ProjectWorkshop />} />
          <Route path="/projects/:id/worldview" element={<WorldviewPage />} />
          <Route path="/projects/:id/characters" element={<CharactersPage />} />
          <Route path="/projects/:id/outline" element={<OutlinePage />} />
          <Route path="/projects/:id/writing" element={<WritingPage />} />
          <Route path="/projects/:id/foreshadowing" element={<ForeshadowingPage />} />
          <Route path="/projects/:id/consistency" element={<ConsistencyPage />} />
          <Route path="/projects/:id/knowledge" element={<KnowledgePage />} />
          <Route path="/projects/:id/reader" element={<ReaderPage />} />
          <Route path="/projects/:id/settings" element={<ProjectSettingsPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Routes>
      </BrowserRouter>
    </ConfigProvider>
  );
}

export default App;