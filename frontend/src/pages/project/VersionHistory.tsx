// @ts-nocheck
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { useEffect, useState } from 'react';
import {
  Card,
  Spin,
  message,
  Button,
  List,
  Typography,
  Space,
  Descriptions,
  Modal,
  Empty,
  Tag,
  Divider,
  Select,
} from 'antd';
import {
  HistoryOutlined,
  ArrowLeftOutlined,
  RollbackOutlined,
  EyeOutlined,
  CopyOutlined,
} from '@ant-design/icons';
import AppLayout from '../../components/layout/AppLayout';
import VersionDiffModal from '../../components/VersionDiffModal';
import { versionApi, chapterApi, type VersionEntry, type VersionDetail, type Chapter } from '../../services/api';

const { Title, Text, Paragraph } = Typography;

export default function VersionHistoryPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const searchParams = new URLSearchParams(location.search);
  const queryChapterId = searchParams.get('chapter') || '';
  const [chapterId, setChapterId] = useState<string>(queryChapterId);
  const [chapterTitle, setChapterTitle] = useState('');
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [loading, setLoading] = useState(false);
  const [preview, setPreview] = useState<VersionDetail | null>(null);
  const [restoring, setRestoring] = useState<number | null>(null);
  const [history, setHistory] = useState<VersionEntry[]>([]);
  const [currentVersion, setCurrentVersion] = useState(0);
  const [diffOpen, setDiffOpen] = useState(false);

  const projectId = id || '';

  const loadChapters = async () => {
    if (!projectId) return;
    try {
      const { data } = await chapterApi.list(projectId);
      const list = Array.isArray(data) ? data : [];
      setChapters(list);
      // Auto-select first chapter if none selected
      if (!chapterId && list.length > 0) {
        setChapterId(list[0].id);
      }
    } catch {
      // non-blocking
    }
  };

  const loadVersions = async (cid: string) => {
    if (!projectId || !cid) return;
    setLoading(true);
    try {
      const { data } = await versionApi.list(projectId, cid);
      setHistory(data.versions || []);
      setCurrentVersion(data.current_version || 0);
      setChapterId(cid);
    } catch {
      message.error('加载版本历史失败');
      setHistory([]);
    } finally {
      setLoading(false);
    }
  };

  const loadChapterTitle = async (cid: string) => {
    if (!projectId || !cid) return;
    const ch = chapters.find((c: Chapter) => c.id === cid);
    if (ch) {
      setChapterTitle(`${ch.chapter_number}：${ch.title}`);
      return;
    }
    try {
      const { data } = await chapterApi.list(projectId);
      const found = data?.find((c: Chapter) => c.id === cid);
      setChapterTitle(found ? `${found.chapter_number}：${found.title}` : '');
    } catch {
      // non-blocking
    }
  };

  useEffect(() => {
    loadChapters();
  }, [projectId]);

  useEffect(() => {
    if (chapterId) {
      loadVersions(chapterId);
      loadChapterTitle(chapterId);
    }
  }, [chapterId]);

  const handlePreview = async (entry: VersionEntry) => {
    try {
      const { data } = await versionApi.get(projectId, chapterId, entry.version);
      setPreview(data);
    } catch {
      message.error('加载版本内容失败');
    }
  };

  const handleRestore = async (entry: VersionEntry) => {
    if (!chapterId) return;
    const confirmOk = window.confirm(
      `确定要恢复到版本 ${entry.version}（${entry.saved_at}）吗？\n当前内容也会被保存为一个新历史记录。`
    );
    if (!confirmOk) return;
    setRestoring(entry.version);
    try {
      const { data } = await versionApi.restore(projectId, chapterId, entry.version);
      message.success(`已恢复到版本 ${entry.version}，当前版本号：${data.version || currentVersion + 1}`);
      loadVersions(chapterId);
      loadChapterTitle(chapterId);
    } catch {
      message.error('恢复失败');
    } finally {
      setRestoring(null);
    }
  };

  const renderContentPreview = (detail: VersionDetail) => {
    let text = '';
    if (detail.content) {
      if (typeof detail.content === 'string') text = detail.content;
      else if (typeof detail.content === 'object' && 'text' in detail.content) {
        text = detail.content.text || '';
      }
    }
    if (!text) return <Text type="secondary">此版本无正文内容</Text>;
    return (
      <div
        style={{
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-word',
          maxHeight: 520,
          overflow: 'auto',
          background: '#FAFAFA',
          padding: 16,
          borderRadius: 6,
          fontSize: 14,
          lineHeight: 1.7,
        }}
      >
        {text}
      </div>
    );
  };

  const formatDate = (iso: string) => {
    if (!iso) return '—';
    return new Date(iso).toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  };

  return (
    <AppLayout projectId={projectId}>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 24,
          flexWrap: 'wrap',
          gap: 12,
        }}
      >
        <Space>
          <Button type="text" icon={<ArrowLeftOutlined />} onClick={() => navigate(`/projects/${projectId}/writing`)}>
            返回写作
          </Button>
          <Title level={3} style={{ margin: 0 }}>
            版本历史
          </Title>
          {chapterTitle && <Text type="secondary">{chapterTitle}</Text>}
        </Space>
        <Space>
          <Select
            style={{ minWidth: 240 }}
            placeholder="选择章节"
            value={chapterId || undefined}
            onChange={(val) => setChapterId(val)}
            options={chapters.map(ch => ({
              value: ch.id,
              label: `第${ch.chapter_number}章 ${ch.title}`,
            }))}
          />
          <Text type="secondary">版本号：{currentVersion}</Text>
        </Space>
      </div>

      <Card title={<Space><HistoryOutlined /> 版本列表</Space>}
        extra={
          history.length >= 2 ? (
            <Button icon={<EyeOutlined />} onClick={() => setDiffOpen(true)}>
              版本对比
            </Button>
          ) : null
        }
      >
        {loading ? (
          <div style={{ display: 'flex', justifyContent: 'center', padding: 60 }}>
            <Spin />
          </div>
        ) : history.length === 0 ? (
          <Empty description="暂无版本历史（章节尚未进行过保存）">
            <Button onClick={() => navigate(`/projects/${projectId}/writing`)}>前往写作页保存章节</Button>
          </Empty>
        ) : (
          <List
            dataSource={history}
            locale={{ emptyText: '无版本' }}
            renderItem={(entry: VersionEntry, idx: number) => (
              <List.Item
                key={`${entry.version}-${idx}`}
                style={{ borderBottom: '1px solid #f0f0f0' }}
              >
                <div style={{ flex: 1 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                    <Tag color="blue">v{entry.version}</Tag>
                    <Text strong>版本 {entry.version}</Text>
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      hash: {entry.content_hash}
                    </Text>
                  </div>
                  <Descriptions size="small" column={2} style={{ marginBottom: 4 }}>
                    <Descriptions.Item label="保存时间">{formatDate(entry.saved_at)}</Descriptions.Item>
                    <Descriptions.Item label="字数">{entry.word_count}</Descriptions.Item>
                  </Descriptions>
                </div>
                <Space>
                  <Button
                    size="small"
                    icon={<EyeOutlined />}
                    onClick={() => handlePreview(entry)}
                  >
                    预览
                  </Button>
                  <Button
                    size="small"
                    type="primary"
                    icon={<RollbackOutlined />}
                    loading={restoring === entry.version}
                    onClick={() => handleRestore(entry)}
                  >
                    恢复
                  </Button>
                </Space>
              </List.Item>
            )}
          />
        )}
      </Card>

      {chapterId && (
        <VersionDiffModal
          open={diffOpen}
          onClose={() => setDiffOpen(false)}
          projectId={projectId}
          chapterId={chapterId}
          versions={history}
        />
      )}

      <Modal
        title={<Space><EyeOutlined /> 版本内容预览 v{preview?.version}</Space>}
        open={!!preview}
        onCancel={() => setPreview(null)}
        footer={
          <Space>
            <Button onClick={() => setPreview(null)}>关闭</Button>
            {preview && (
              <Button
                type="primary"
                icon={<RollbackOutlined />}
                onClick={() => {
                  handleRestore(preview);
                  setPreview(null);
                }}
              >
                恢复此版本
              </Button>
            )}
          </Space>
        }
        width={760}
      >
        {preview && (
          <>
            <Descriptions size="small" column={3} style={{ marginBottom: 12 }}>
              <Descriptions.Item label="版本">v{preview.version}</Descriptions.Item>
              <Descriptions.Item label="字数">{preview.word_count}</Descriptions.Item>
              <Descriptions.Item label="保存时间">{formatDate(preview.saved_at)}</Descriptions.Item>
            </Descriptions>
            <Divider style={{ margin: '8px 0' }} />
            {renderContentPreview(preview)}
          </>
        )}
      </Modal>
    </AppLayout>
  );
}
