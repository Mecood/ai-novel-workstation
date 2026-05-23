import { useEffect, useState } from 'react';
import { useNavigate, useLocation, useParams } from 'react-router-dom';
import { Breadcrumb, Layout, Menu, Typography } from 'antd';
import {
  HomeOutlined,
  GlobalOutlined,
  TeamOutlined,
  OrderedListOutlined,
  EditOutlined,
  LinkOutlined,
  CheckCircleOutlined,
  SettingOutlined,
  ReadOutlined,
  BookOutlined,
  ExperimentOutlined,
  ExportOutlined,
  ArrowLeftOutlined,
} from '@ant-design/icons';
import type { ReactNode } from 'react';
import { projectApi, type Project } from '../../services/api';

const { Sider, Content } = Layout;
const { Title } = Typography;

const menuItems = [
  { key: 'workshop', icon: <HomeOutlined />, label: '创作工坊' },
  { key: 'worldview', icon: <GlobalOutlined />, label: '世界观' },
  { key: 'characters', icon: <TeamOutlined />, label: '角色' },
  { key: 'outline', icon: <OrderedListOutlined />, label: '大纲规划' },
  { key: 'writing', icon: <EditOutlined />, label: '写作' },
  { key: 'foreshadowing', icon: <LinkOutlined />, label: '伏笔' },
  { key: 'consistency', icon: <CheckCircleOutlined />, label: '一致性' },
  { key: 'knowledge', icon: <BookOutlined />, label: '知识库' },
  { key: 'reader', icon: <ReadOutlined />, label: '阅读器' },
  { type: 'divider' as const },
  { key: 'settings', icon: <SettingOutlined />, label: '项目设置' },
];

const menuLabelMap = menuItems.reduce<Record<string, string>>((acc, item) => {
  if ('key' in item && item.key && typeof item.label === 'string') {
    acc[item.key] = item.label;
  }
  return acc;
}, {});

interface AppLayoutProps {
  projectId: string;
  children: ReactNode;
}

export default function AppLayout({ projectId, children }: AppLayoutProps) {
  const navigate = useNavigate();
  const location = useLocation();
  const { id } = useParams<{ id: string }>();
  const activeKey = location.pathname.split('/').pop() || 'workshop';
  const [project, setProject] = useState<Project | undefined>(undefined);

  useEffect(() => {
    if (!id) return;
    projectApi
      .get(id)
      .then((res) => setProject(res.data))
      .catch(() => setProject(undefined));
  }, [id]);

  const onMenuClick = ({ key }: { key: string }) => {
    navigate(`/projects/${projectId}/${key}`);
  };

  return (
    <Layout style={{ minHeight: '100vh', background: '#FAFAFA' }}>
      <Sider
        width={240}
        style={{
          background: '#fff',
          borderRight: '1px solid #f0f0f0',
          height: '100vh',
          position: 'fixed',
          left: 0,
          top: 0,
          overflow: 'auto',
        }}
      >
        <div
          onClick={() => navigate('/')}
          style={{
            height: 64,
            display: 'flex',
            alignItems: 'center',
            paddingLeft: 24,
            borderBottom: '1px solid #f0f0f0',
            cursor: 'pointer',
            transition: 'background-color 0.2s',
          }}
          onMouseEnter={(e) => {
            (e.currentTarget as HTMLDivElement).style.backgroundColor = '#F5F7FA';
          }}
          onMouseLeave={(e) => {
            (e.currentTarget as HTMLDivElement).style.backgroundColor = 'transparent';
          }}
        >
          <ArrowLeftOutlined style={{ color: '#5B9BD5', fontSize: 16, marginRight: 8 }} />
          <Title level={4} style={{ margin: 0, color: '#5B9BD5', fontWeight: 700 }}>
            AI 小说创作
          </Title>
        </div>
        <Menu
          mode="inline"
          selectedKeys={[activeKey]}
          items={menuItems}
          onClick={onMenuClick}
          style={{ borderRight: 'none', marginTop: 8 }}
        />
      </Sider>
      <Layout style={{ marginLeft: 240, background: '#FAFAFA' }}>
        <Content style={{ padding: 24, minHeight: '100vh' }}>
          <Breadcrumb
            style={{ marginBottom: 16 }}
            items={[
              {
                title: (
                  <span onClick={() => navigate('/')} style={{ cursor: 'pointer' }}>
                    项目列表
                  </span>
                ),
              },
              { title: project?.name || '加载中...' },
              ...(activeKey !== 'workshop'
                ? [{ title: menuLabelMap[activeKey] || activeKey }]
                : []),
            ]}
          />
          {children}
        </Content>
      </Layout>
    </Layout>
  );
}
