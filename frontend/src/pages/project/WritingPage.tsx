import { useParams } from 'react-router-dom';
import { useEffect, useState, useRef, useCallback } from 'react';
import { Card, Spin, message, Button, Typography, List, Tag, Empty, Input, Space, Popconfirm } from 'antd';
import { EditOutlined, ThunderboltOutlined, EyeOutlined, SendOutlined, DeleteOutlined } from '@ant-design/icons';
import AppLayout from '../../components/layout/AppLayout';
import { chapterApi, aiApi } from '../../services/api';
import type { Chapter } from '../../services/api';

const { Title, Paragraph, Text } = Typography;
const { TextArea } = Input;

export default function WritingPage() {
  const { id } = useParams<{ id: string }>();
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [streamContent, setStreamContent] = useState('');
  const [selectedChapter, setSelectedChapter] = useState<Chapter | null>(null);
  const [editingContent, setEditingContent] = useState('');
  const streamRef = useRef<HTMLDivElement>(null);

  const fetchData = useCallback(() => {
    if (!id) return;
    setLoading(true);
    chapterApi.list(id).then(({ data }) => {
      const list = Array.isArray(data) ? data : [];
      setChapters(list);
    }).catch(() => {
      message.error('加载章节失败');
    }).finally(() => setLoading(false));
  }, [id]);

  useEffect(() => { fetchData(); }, [fetchData]);
  useEffect(() => { if (streamRef.current) streamRef.current.scrollTop = streamRef.current.scrollHeight; }, [streamContent]);

  const handleGenerate = async () => {
    if (!id) return;
    setGenerating(true);
    setStreamContent('');
    try {
      await aiApi.generateChapter(id, (chunk) => {
        setStreamContent((prev) => prev + chunk);
      });
      message.success('章节生成完成');
      fetchData();
    } catch (err) {
      message.error('生成失败');
    } finally {
      setGenerating(false);
    }
  };

  const handleSelectChapter = (ch: Chapter) => {
    setSelectedChapter(ch);
    const content = typeof ch.content === 'string' ? ch.content : JSON.stringify(ch.content || '');
    setEditingContent(content);
  };

  const handleSave = async () => {
    if (!id || !selectedChapter) return;
    setSaving(true);
    try {
      await chapterApi.update(id, selectedChapter.id, {
        content: editingContent,
        title: selectedChapter.title,
        status: selectedChapter.status,
        word_count: editingContent.length,
      } as any);
      message.success('保存成功');
      fetchData();
    } catch (err) {
      message.error('保存失败');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (ch: Chapter) => {
    if (!id) return;
    try {
      await chapterApi.delete(id, ch.id);
      message.success('删除成功');
      if (selectedChapter?.id === ch.id) {
        setSelectedChapter(null);
        setEditingContent('');
      }
      fetchData();
    } catch (err) {
      message.error('删除失败');
    }
  };

  return (
    <AppLayout projectId={id!}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <Title level={3} style={{ margin: 0 }}>写作工作区</Title>
        <Button type="primary" icon={<ThunderboltOutlined />} loading={generating} onClick={handleGenerate}>
          AI 生成章节
        </Button>
      </div>

      <div style={{ display: 'flex', gap: 16 }}>
        {/* 左侧章节列表 */}
        <Card title="章节目录" style={{ width: 280, flexShrink: 0 }}>
          {loading ? <Spin /> : chapters.length === 0 ? (
            <Empty description="暂无章节" />
          ) : (
            <List
              size="small"
              dataSource={chapters}
              renderItem={(ch) => (
                <List.Item
                  onClick={() => handleSelectChapter(ch)}
                  style={{ cursor: 'pointer', background: selectedChapter?.id === ch.id ? '#e6f4ff' : undefined }}
                  actions={[
                    <Popconfirm
                      key="delete"
                      title={`确认删除第${ch.chapter_number}章？`}
                      onConfirm={(e) => {
                        e?.stopPropagation();
                        handleDelete(ch);
                      }}
                      onCancel={(e) => e?.stopPropagation()}
                      okText="确认"
                      cancelText="取消"
                    >
                      <Button
                        type="text"
                        size="small"
                        danger
                        icon={<DeleteOutlined />}
                        onClick={(e) => e.stopPropagation()}
                      />
                    </Popconfirm>,
                  ]}
                >
                  <List.Item.Meta
                    title={<Text strong>第{ch.chapter_number}章 {ch.title}</Text>}
                    description={
                      <Space>
                        <Tag>{ch.status}</Tag>
                        <Text type="secondary">{ch.word_count}字</Text>
                      </Space>
                    }
                  />
                </List.Item>
              )}
            />
          )}
        </Card>

        {/* 右侧写作区 */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* 流式生成区域 */}
          {streamContent && (
            <Card
              title="正在生成..."
              ref={streamRef}
              style={{ maxHeight: 300, overflow: 'auto', background: '#f6ffed' }}
            >
              <Paragraph>{streamContent}</Paragraph>
            </Card>
          )}

          {/* 章节编辑区 */}
          {selectedChapter ? (
            <Card
              title={`第${selectedChapter.chapter_number}章 ${selectedChapter.title}`}
              extra={<Button icon={<EyeOutlined />} onClick={() => message.info('预览功能开发中')}>预览</Button>}
            >
              <TextArea
                value={editingContent}
                onChange={(e) => setEditingContent(e.target.value)}
                rows={16}
                style={{ fontFamily: 'inherit', lineHeight: 1.8 }}
              />
              <div style={{ textAlign: 'right', marginTop: 12 }}>
                <Button type="primary" icon={<SendOutlined />} loading={saving} onClick={handleSave}>保存</Button>
              </div>
            </Card>
          ) : (
            <Card>
              <Empty description="从左侧选择章节开始编辑，或点击上方按钮 AI 生成新章节" />
            </Card>
          )}
        </div>
      </div>
    </AppLayout>
  );
}
