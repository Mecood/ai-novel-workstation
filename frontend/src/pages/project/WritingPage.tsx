import { useParams } from 'react-router-dom';
import { useEffect, useState, useRef, useCallback } from 'react';
import { Card, Spin, message, Button, Typography, List, Tag, Empty, Input, Space, Popconfirm, Collapse, Alert, Modal } from 'antd';
import { EditOutlined, ThunderboltOutlined, EyeOutlined, SendOutlined, DeleteOutlined, BookOutlined } from '@ant-design/icons';
import AppLayout from '../../components/layout/AppLayout';
import { chapterApi, aiApi, foreshadowingApi } from '../../services/api';
import type { Chapter } from '../../services/api';

const { Title, Paragraph, Text } = Typography;
const { TextArea } = Input;

export default function WritingPage() {
  const { id } = useParams<{ id: string }>();
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [streamContent, setStreamContent] = useState('');
  const accumulatedRef = useRef('');
  const [selectedChapter, setSelectedChapter] = useState<Chapter | null>(null);
  const [editingContent, setEditingContent] = useState('');
  const [previousSummary, setPreviousSummary] = useState<string | null>(null);
  const [summaryChapterCount, setSummaryChapterCount] = useState(0);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [unresolvedCount, setUnresolvedCount] = useState(0);
  const [unresolvedOverdue, setUnresolvedOverdue] = useState(0);
  const [previewOpen, setPreviewOpen] = useState(false);
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

  const fetchPreviousSummary = useCallback((currentChapter?: number) => {
    if (!id) return;
    setSummaryLoading(true);
    chapterApi.previousSummary(id, currentChapter).then(({ data }) => {
      setPreviousSummary(data.summary);
      setSummaryChapterCount(data.chapter_count);
    }).catch(() => {
      setPreviousSummary(null);
      setSummaryChapterCount(0);
    }).finally(() => setSummaryLoading(false));
  }, [id]);

  useEffect(() => { fetchData(); }, [fetchData]);
  useEffect(() => {
    if (!id) return;
    foreshadowingApi.getUnresolved(id).then(({ data }) => {
      setUnresolvedCount(data.count);
      setUnresolvedOverdue(data.overdue);
    }).catch(() => {
      setUnresolvedCount(0);
      setUnresolvedOverdue(0);
    });
  }, [id]);
  useEffect(() => { if (streamRef.current) streamRef.current.scrollTop = streamRef.current.scrollHeight; }, [streamContent]);

  const handleGenerate = async () => {
    if (!id) return;
    setGenerating(true);
    setStreamContent('');
    accumulatedRef.current = '';
    try {
      await aiApi.generateChapter(
        id,
        (chunk) => {
          accumulatedRef.current += chunk;
          setStreamContent((prev) => prev + chunk);
        },
        (doneData) => {
          const full = accumulatedRef.current;
          const newChapter = {
            id: doneData.chapter_id,
            project_id: id,
            chapter_number: doneData.chapter_number,
            title: doneData.title || `第${doneData.chapter_number}章`,
            content: { text: full },
            summary: '',
            word_count: doneData.word_count || full.length,
            status: 'generated',
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          } as Chapter;
          setSelectedChapter(newChapter);
          setEditingContent(full);
          setStreamContent('');
        }
      );
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
    // 提取文本内容，支持 {text: "..."} 格式
    let content = '';
    if (typeof ch.content === 'string') {
      content = ch.content;
    } else if (ch.content && typeof ch.content === 'object' && 'text' in ch.content) {
      content = (ch.content as { text?: string }).text || '';
    } else if (ch.content) {
      content = JSON.stringify(ch.content);
    }
    setEditingContent(content);
    fetchPreviousSummary(ch.chapter_number);
  };

  const handleSave = async (contentOverride?: string) => {
    if (!id || !selectedChapter) return;
    const content = typeof contentOverride === 'string' ? contentOverride : editingContent;
    setSaving(true);
    try {
      await chapterApi.update(id, selectedChapter.id, {
        content: { text: content },
        title: selectedChapter.title,
        status: selectedChapter.status,
        word_count: content.length,
      } as any);
      message.success('保存成功');
      fetchData();
    } catch (err) {
      message.error('保存失败');
    } finally {
      setSaving(false);
    }
  };

  const handleRegenerate = async () => {
    if (!id || !selectedChapter) return;
    setRegenerating(true);
    setStreamContent('');
    accumulatedRef.current = '';
    try {
      await chapterApi.regenerate(
        id,
        selectedChapter.id,
        (chunk) => {
          accumulatedRef.current += chunk;
          setStreamContent((prev) => prev + chunk);
        },
        (doneData) => {
          const full = accumulatedRef.current;
          setEditingContent(full);
          setSelectedChapter({
            ...selectedChapter,
            content: { text: full },
            word_count: doneData.word_count || full.length,
          });
          setStreamContent('');
        }
      );
      message.success('重新生成完成');
      fetchData();
    } catch (err) {
      message.error('重新生成失败');
    } finally {
      setRegenerating(false);
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

      {/* 未回收伏笔提醒 */}
      {unresolvedCount > 0 && (
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 16 }}
          message={
            <span>
              有 <Text strong>{unresolvedCount}</Text> 个伏笔未回收（其中{' '}
              <Text strong style={{ color: unresolvedOverdue > 0 ? '#cf1322' : undefined }}>
                {unresolvedOverdue}
              </Text>{' '}
              个已逾期），建议在编写本段时安排回收
            </span>
          }
        />
      )}

      {/* 前情提要折叠面板 */}
      <Collapse
        style={{ marginBottom: 16, background: '#fafafa' }}
        items={[
          {
            key: 'previous-summary',
            label: (
              <Space>
                <BookOutlined />
                <Text strong>前情提要</Text>
                {summaryChapterCount > 0 && (
                  <Text type="secondary">基于前 {summaryChapterCount} 章自动生成</Text>
                )}
              </Space>
            ),
            children: summaryLoading ? (
              <Spin />
            ) : previousSummary ? (
              <Paragraph
                style={{
                  whiteSpace: 'pre-wrap',
                  fontFamily: 'inherit',
                  lineHeight: 1.8,
                  margin: 0,
                }}
              >
                {previousSummary}
              </Paragraph>
            ) : (
              <Text type="secondary">
                {selectedChapter
                  ? selectedChapter.chapter_number <= 1
                    ? '这是第一章，没有前情提要'
                    : '前面的章节暂无摘要内容'
                  : '请从左侧选择章节查看前情提要'}
              </Text>
            ),
          },
        ]}
      />

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
                    title={<Text strong>{ch.title?.startsWith('第') ? ch.title : `第${ch.chapter_number}章 ${ch.title}`}</Text>}
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
              title={generating ? "正在生成..." : "生成完成"}
              ref={streamRef}
              style={{ maxHeight: 300, overflow: 'auto', background: generating ? '#f6ffed' : '#fff' }}
            >
              <Paragraph style={{ whiteSpace: 'pre-wrap', lineHeight: 1.8 }}>{streamContent}</Paragraph>
            </Card>
          )}

          {/* 章节编辑区 */}
          {selectedChapter ? (
            <Card
              title={selectedChapter.title?.startsWith('第') ? selectedChapter.title : `第${selectedChapter.chapter_number}章 ${selectedChapter.title}`}
              extra={<Button icon={<EyeOutlined />} onClick={() => setPreviewOpen(true)}>预览</Button>}
            >
              <TextArea
                value={editingContent}
                onChange={(e) => setEditingContent(e.target.value)}
                rows={16}
                style={{ fontFamily: 'inherit', lineHeight: 1.8 }}
              />
              <div style={{ textAlign: 'right', marginTop: 12 }}>
                <Space>
                  <Popconfirm
                    title="确认重新生成此章节？"
                    description="已编辑的内容将被替换为 AI 重新生成的内容，且无法恢复。"
                    onConfirm={handleRegenerate}
                    okText="确认重新生成"
                    cancelText="取消"
                    okButtonProps={{ danger: true }}
                  >
                    <Button icon={<ThunderboltOutlined />} loading={regenerating} disabled={saving}>
                      重新生成
                    </Button>
                  </Popconfirm>
                  <Button type="primary" icon={<SendOutlined />} loading={saving} disabled={regenerating} onClick={() => handleSave()}>保存</Button>
                </Space>
              </div>
            </Card>
          ) : (
            <Card>
              <Empty description="从左侧选择章节开始编辑，或点击上方按钮 AI 生成新章节" />
            </Card>
          )}
        </div>
      </div>

      {/* 预览弹窗 */}
      <Modal
        title={selectedChapter ? `${selectedChapter.title?.startsWith('第') ? selectedChapter.title : `第${selectedChapter.chapter_number}章 ${selectedChapter.title}`} - 预览` : '预览'}
        open={previewOpen}
        onCancel={() => setPreviewOpen(false)}
        footer={[
          <Button key="close" onClick={() => setPreviewOpen(false)}>关闭</Button>,
        ]}
        width={800}
      >
        <div style={{ whiteSpace: 'pre-wrap', lineHeight: 2, fontSize: 16, padding: '8px 0' }}>
          {editingContent || '暂无内容'}
        </div>
      </Modal>
    </AppLayout>
  );
}
