// @ts-nocheck
import { useParams } from 'react-router-dom';
import { useState, useCallback, useEffect } from 'react';
import {
  Card, Spin, Button, Typography, Select, Space, Empty, Collapse, Tag, message, Divider,
} from 'antd';
import {
  FileTextOutlined, EyeOutlined, ReloadOutlined,
} from '@ant-design/icons';
import AppLayout from '../../components/layout/AppLayout';
import { chapterApi, api } from '../../services/api';

const { Title, Paragraph, Text } = Typography;

// 五段标签
const SECTION_LABELS: Record<string, { label: string; color: string; icon: string }> = {
  '开篇委托': { label: '开篇委托', color: '#5B9BD5', icon: '📖' },
  '这章的故事': { label: '这章的故事', color: '#52c41a', icon: '🎯' },
  '这章的人物': { label: '这章的人物', color: '#faad14', icon: '👥' },
  '怎么写更顺': { label: '怎么写更顺', color: '#eb2f96', icon: '✍️' },
  '收在哪里': { label: '收在哪里', color: '#722ed1', icon: '🎬' },
};

function parseSections(taskBook: string): { title: string; content: string }[] {
  if (!taskBook) return [];
  const parts = taskBook.split(/^---$/m).map(s => s.trim()).filter(Boolean);
  const result: { title: string; content: string }[] = [];
  for (const part of parts) {
    // 尝试从第一行提取标题
    const firstLine = part.split('\n')[0].replace(/^#+\s*/, '').replace(/\*\*/g, '').trim();
    const content = part.split('\n').slice(1).join('\n').trim();
    const label = SECTION_LABELS[firstLine] || SECTION_LABELS[Object.keys(SECTION_LABELS).find(k => firstLine.includes(k)) || ''];
    result.push({
      title: label?.label || firstLine || '未命名段落',
      content: content || part,
    });
  }
  return result;
}

export default function ContextAgentView() {
  const { id } = useParams<{ id: string }>();
  const [chapters, setChapters] = useState<any[]>([]);
  const [selectedChapter, setSelectedChapter] = useState<number | undefined>(undefined);
  const [loading, setLoading] = useState(false);
  const [taskBook, setTaskBook] = useState('');
  const [taskMeta, setTaskMeta] = useState<{ title: string; status: string } | null>(null);

  useEffect(() => {
    if (!id) return;
    chapterApi.list(id).then(({ data }) => {
      const sorted = [...data].sort((a: any, b: any) => a.chapter_number - b.chapter_number);
      setChapters(sorted);
      const last = sorted[sorted.length - 1];
      if (last) setSelectedChapter(last.chapter_number);
    }).catch(() => {});
  }, [id]);

  const fetchTaskBook = useCallback(async (chapterNum: number) => {
    if (!id) return;
    setLoading(true);
    setTaskBook('');
    setTaskMeta(null);
    try {
      const { data } = await api.get(`/projects/${id}/chapters/${chapterNum}/task-book`);
      setTaskBook(data.task_book || '');
      setTaskMeta({ title: data.chapter_title || '', status: data.chapter_status || '' });
    } catch (e: any) {
      message.error('获取任务书失败：' + (e?.message || '未知错误'));
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    if (selectedChapter) fetchTaskBook(selectedChapter);
  }, [selectedChapter, fetchTaskBook]);

  const sections = parseSections(taskBook);

  return (
    <AppLayout projectId={id || ''}>
      <Card
        title={
          <Space>
            <FileTextOutlined style={{ color: '#5B9BD5' }} />
            <span>写作任务书</span>
            <Tag color="blue">Context Agent</Tag>
          </Space>
        }
        extra={
          <Space>
            <Select
              style={{ width: 160 }}
              placeholder="选择章节"
              value={selectedChapter}
              onChange={(v) => setSelectedChapter(v)}
              options={chapters.map((c) => ({
                value: c.chapter_number,
                label: `第${c.chapter_number}章 ${c.title || ''}`,
              }))}
            />
            <Button
              icon={<ReloadOutlined />}
              onClick={() => selectedChapter && fetchTaskBook(selectedChapter)}
              loading={loading}
            >
              刷新
            </Button>
          </Space>
        }
      >
        {taskMeta && (
          <div style={{ marginBottom: 16 }}>
            <Space size="middle">
              <Text strong>当前章节：</Text>
              <Tag color="blue">第{selectedChapter}章</Tag>
              {taskMeta.title && <Text>{taskMeta.title}</Text>}
              {taskMeta.status && (
                <Tag color={taskMeta.status === 'generated' ? 'green' : taskMeta.status === 'outlined' ? 'orange' : 'default'}>
                  {taskMeta.status === 'generated' ? '已生成' : taskMeta.status === 'outlined' ? '已规划' : taskMeta.status}
                </Tag>
              )}
            </Space>
          </div>
        )}

        <Spin spinning={loading} tip="正在组装写作任务书...">
          {sections.length > 0 ? (
            <Collapse
              defaultActiveKey={sections.map((_, i) => String(i))}
              items={sections.map((sec, i) => {
                const labelInfo = Object.values(SECTION_LABELS).find(l => sec.title.includes(l.label));
                return {
                  key: String(i),
                  label: (
                    <Space>
                      <span style={{ fontSize: 16 }}>{labelInfo?.icon || '📝'}</span>
                      <span style={{ fontWeight: 600, color: labelInfo?.color }}>{sec.title}</span>
                    </Space>
                  ),
                  children: (
                    <div style={{ whiteSpace: 'pre-wrap', lineHeight: 1.8, fontSize: 14, color: '#333' }}>
                      {sec.content}
                    </div>
                  ),
                };
              })}
            />
          ) : (
            !loading && (
              <Empty
                description="暂无任务书数据。请确保项目已有故事核心、世界观、角色和大纲。"
                image={Empty.PRESENTED_IMAGE_SIMPLE}
              />
            )
          )}
        </Spin>

        <Divider />
        <Paragraph type="secondary" style={{ fontSize: 12 }}>
          💡 任务书基于项目的故事核心、世界观、角色、章纲、伏笔和记忆系统自动组装。
          它会告诉你这章该怎么写——但不会替你写。真正的写作依然在「写作」页面进行。
        </Paragraph>
      </Card>
    </AppLayout>
  );
}
