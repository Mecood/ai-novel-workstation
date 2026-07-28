// @ts-nocheck
import { useParams } from 'react-router-dom';
import { useEffect, useState, useRef, useCallback } from 'react';
import { Card, Spin, message, Button, Typography, List, Tag, Empty, Input, InputNumber, Space, Popconfirm, Collapse, Alert, Modal, Select } from 'antd';
import { FileTextOutlined, SyncOutlined, EditOutlined, ThunderboltOutlined, EyeOutlined, SendOutlined, DeleteOutlined, BookOutlined, ExperimentOutlined, MedicineBoxOutlined, BarChartOutlined, FolderOutlined, PlusOutlined, RobotOutlined } from '@ant-design/icons';
import AppLayout from '../../components/layout/AppLayout';
import TiptapEditor from '../../components/editor/TiptapEditor';
import WritingCompanionPanel from './components/WritingCompanionPanel';
import { chapterApi, aiApi, foreshadowingApi, eventApi, debtApi, contractApi, DEBT_TYPE_LABELS, HOOK_TYPE_LABELS, HOOK_STRENGTH_LABELS, CONTRACT_STATUS_LABELS, COMMIT_STATUS_LABELS, EVENT_TYPE_LABELS, STAGE_LABELS, autoPipelineApi } from '../../services/api';
import type { Chapter, StoryEvent, ReadingPowerEvalResult, ChapterContract, ChapterCommit, ChapterSkeleton, PipelineStageEvent, PipelineProgress } from '../../services/api';

const { Title, Paragraph, Text } = Typography;

export default function WritingPage() {
  const { id } = useParams<{ id: string }>();
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [streamContent, setStreamContent] = useState('');

  // ── Phase 13.1：流水线状态 ────────────────────────────────────────────
  const [pipelineStage, setPipelineStage] = useState<string>('');
  const [pipelineDone, setPipelineDone] = useState<boolean>(false);
  const [pipelineResult, setPipelineResult] = useState<any>(null);
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
  const [deAing, setDeAing] = useState(false);
  const [detectLoading, setDetectLoading] = useState(false);
  const [aiReport, setAiReport] = useState<{
    score: number; level: string;
    issues: Array<{ type: string; severity: string; text: string; line: number; suggestion: string }>;
    stats: { total_chars: number; cliche_count: number; issue_count: number; sentence_avg_len: number; paragraph_count: number };
  } | null>(null);
  const [extracting, setExtracting] = useState(false);
  const [lastExtractEvents, setLastExtractEvents] = useState<StoryEvent[]>([]);
  const [lastExtractChapter, setLastExtractChapter] = useState<number>(0);
  const [selectedChapterNum, setSelectedChapterNum] = useState<number>(1);
  const [evalResult, setEvalResult] = useState<ReadingPowerEvalResult | null>(null);
  const [companionOpen, setCompanionOpen] = useState(false);
  const [evaluating, setEvaluating] = useState(false);
  const [evalChapterNum, setEvalChapterNum] = useState<number>(1);
  // ── 分组 / 标签 ────────────────────────────────────────────
  const [groupFilter, setGroupFilter] = useState<string | undefined>();
  const [tagFilter, setTagFilter] = useState<string | undefined>();
  const [collapsedGroups, setCollapsedGroups] = useState<Record<string, boolean>>({});

  // ── 合同系统状态 ────────────────────────────────────────────────────
  const [contract, setContract] = useState<ChapterContract | null>(null);
  const [contractLoading, setContractLoading] = useState(false);
  const [signing, setSigning] = useState(false);
  const [commit, setCommit] = useState<ChapterCommit | null>(null);
  const [commitLoading, setCommitLoading] = useState(false);
  const [committing, setCommitting] = useState(false);

  // ── 未保存内容保护 ────────────────────────────────────────────────
  const isDirty = useRef(false);
  const lastSavedContent = useRef('');

  const checkDirty = useCallback(() => {
    return editingContent !== lastSavedContent.current;
  }, [editingContent]);

  // beforeunload 提醒
  useEffect(() => {
    const handler = (e: BeforeUnloadEvent) => {
      if (checkDirty()) {
        e.preventDefault();
        e.returnValue = '';
      }
    };
    window.addEventListener('beforeunload', handler);
    return () => window.removeEventListener('beforeunload', handler);
  }, [checkDirty]);

  const SCORE_COLOR = (score: number) => {
    if (score >= 8) return '#52c41a';
    if (score >= 6) return '#1890ff';
    if (score >= 4) return '#faad14';
    return '#f5222d';
  };

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

  const fetchContract = useCallback(async (ch: number) => {
    if (!id) return;
    setContractLoading(true);
    try {
      const { data } = await contractApi.getContract(id, ch);
      setContract(data);
    } catch {
      setContract(null);
    } finally {
      setContractLoading(false);
    }
  }, [id]);

  const fetchCommit = useCallback(async (ch: number) => {
    if (!id) return;
    setCommitLoading(true);
    try {
      const { data } = await contractApi.getCommit(id, ch);
      setCommit(data);
    } catch {
      setCommit(null);
    } finally {
      setCommitLoading(false);
    }
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

  // ── Autosave：每 30 秒自动保存脏内容 ─────────────────────────────
  useEffect(() => {
    const interval = setInterval(() => {
      if (id && selectedChapter && editingContent && checkDirty() && !saving) {
        handleSave(editingContent);
      }
    }, 30000);
    return () => clearInterval(interval);
  }, [id, selectedChapter, editingContent, saving, checkDirty]);

  // ── 分组 / 标签 工具 ────────────────────────────────────────────
  const groupedChapters = chapters.reduce((acc, ch) => {
    const key = ch.group || '__ungrouped__';
    if (!acc[key]) acc[key] = [];
    acc[key].push(ch);
    return acc;
  }, {} as Record<string, Chapter[]>);
  const groupKeys = Object.keys(groupedChapters).filter(k => k !== '__ungrouped__');
  const allTags = [...new Set(chapters.flatMap(c => (c.tags || [])).filter(Boolean))].sort();
  const groupedTags = [...new Set(groupKeys.map(g => ({ label: g })) )];

  const toggleGroup = (key: string) => {
    setCollapsedGroups(prev => ({ ...prev, [key]: !prev[key] }));
  };

  const handleResetFilter = () => {
    setGroupFilter(undefined);
    setTagFilter(undefined);
    setCollapsedGroups({});
  };

  const getFilteredChapters = (source: Chapter[]) => {
    let out = source;
    if (groupFilter) {
      out = out.filter(c => c.group === groupFilter);
    }
    if (tagFilter) {
      out = out.filter(c => (c.tags || []).includes(tagFilter));
    }
    return out;
  };

  const handleSetGroup = async (ch: Chapter, group: string | null) => {
    if (!id) return;
    try {
      await chapterApi.updateGroupTags(id, ch.id, { group });
      message.success('分组已更新');
      fetchData();
    } catch { message.error('更新失败'); }
  };

  const handleAddTag = async (ch: Chapter, tag: string) => {
    if (!id || !tag.trim()) return;
    tag = tag.trim();
    const newTags = [...(ch.tags || []).filter(t => t !== tag), tag];
    try {
      await chapterApi.updateGroupTags(id, ch.id, { tags: newTags });
      setTagInput('');
      message.success(`已添加标签：${tag}`);
      fetchData();
    } catch { message.error('添加失败'); }
  };

  const handleRemoveTag = async (ch: Chapter, removeTag: string) => {
    if (!id) return;
    const newTags = (ch.tags || []).filter(t => t !== removeTag);
    try {
      await chapterApi.updateGroupTags(id, ch.id, { tags: newTags });
      message.success('已移除标签');
      fetchData();
    } catch { message.error('移除失败'); }
  };

  const handleGenerate = async () => {
    if (!id) return;
    setGenerating(true);
    setStreamContent('');
    accumulatedRef.current = '';
    setPipelineStage('');
    setPipelineDone(false);
    setPipelineResult(null);
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
        },
        // ── Phase 13.1：流水线事件回调 ──────────────────────────────────
        (event) => {
          const eventType = event.type;
          if (eventType === 'info') {
            // 流水线启动通知
            setPipelineStage(event.message || '流水线开始');
          } else if (eventType === 'review_complete') {
            const score = event.data?.overall_score;
            const blocking = event.data?.blocking_count || 0;
            setPipelineStage(`审查完成 — 总分 ${score}，阻断 ${blocking} 项`);
            if (blocking > 0) {
              message.warning(`审查发现 ${blocking} 个阻断问题`);
            }
          } else if (eventType === 'polish_complete') {
            const status = event.data?.status;
            const reason = event.data?.reason;
            const steps = event.data?.steps_completed || 0;
            if (status === 'skipped') {
              setPipelineStage(`润色跳过 — ${reason}`);
            } else if (status === 'error') {
              setPipelineStage(`润色失败 — ${event.data?.error}`);
              message.warning(`润色失败：${event.data?.error}`);
            } else {
              setPipelineStage(`润色完成 — ${steps} 步`);
              message.success(`润色完成（${steps} 步）`);
            }
          } else if (eventType === 'extraction_complete') {
            const count = event.data?.event_count || 0;
            setPipelineStage(`提取完成 — ${count} 个事件`);
          } else if (eventType === 'ai_detect_complete') {
            const score = event.data?.score;
            const needsRewrite = event.data?.needs_rewrite;
            const count = event.data?.detection_count || 0;
            if (needsRewrite) {
              setPipelineStage(`AI味检测 — ${count} 处特征，得分 ${score}，正在重写...`);
              message.warning(`AI味过重（得分 ${score}），自动去AI味重写`);
            } else {
              setPipelineStage(`AI味检测通过 — 得分 ${score}`);
              message.success(`AI味检测通过（得分 ${score}）`);
            }
          } else if (eventType === 'validation_complete') {
            const passed = event.data?.passed;
            const blocking = event.data?.blocking_count || 0;
            const warning = event.data?.warning_count || 0;
            if (passed) {
              setPipelineStage(`校验通过 — ${warning} 个警告`);
              message.success(`写后校验通过`);
            } else {
              setPipelineStage(`校验失败 — ${blocking} 个阻断, ${warning} 个警告`);
              message.error(`写后校验阻断提交：${event.data?.summary}`);
            }
          } else if (eventType === 'commit_blocked') {
            setPipelineStage(`提交阻断 — ${event.data?.reason}`);
            message.error(`提交被阻断：${event.data?.summary}`);
          } else if (eventType === 'debt_complete') {
            const score = event.data?.reading_power_score;
            setPipelineStage(`债务评估完成 — 追读力 ${score}`);
          } else if (eventType === 'commit_complete') {
            setPipelineStage('提交完成');
          } else if (eventType === 'pipeline_complete') {
            setPipelineDone(true);
            setPipelineResult(event.data);
            const status = event.data?.status;
            setPipelineStage(`流水线完成 — ${status}`);
            message.success(`流水线${status === 'completed' ? '全部成功' : '完成（含错误）'}`);
          } else if (eventType === 'pipeline_error') {
            setPipelineDone(true);
            message.error(`流水线错误：${event.data?.error}`);
          } else if (eventType === 'progress') {
            const stage = event.stage;
            const status = event.status;
            setPipelineStage(`${stage} — ${status === 'running' ? '运行中' : '完成'}`);
          }
        },
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
    // 如果当前章有未保存内容，提醒用户
    if (selectedChapter && selectedChapter.id !== ch.id && checkDirty()) {
      Modal.confirm({
        title: '未保存的更改',
        content: '当前章节有未保存的内容，切换将丢失更改。是否继续？',
        okText: '放弃并切换',
        cancelText: '停留',
        onOk: () => {
          _doSelect(ch);
        },
      });
      return;
    }
    _doSelectChapter(ch);
  };

  const _doSelectChapter = (ch: Chapter) => {
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
    lastSavedContent.current = content;
    fetchPreviousSummary(ch.chapter_number);
    // 加载合同信息
    fetchContract(ch.chapter_number);
    fetchCommit(ch.chapter_number);
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
      lastSavedContent.current = content;
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

  const handleDetectAi = async () => {
    if (!id || !selectedChapter) return;
    setDetectLoading(true);
    setAiReport(null);
    try {
      const { data } = await chapterApi.detectAi(id, selectedChapter.id);
      setAiReport(data);
      if (data.score >= 70) message.warning(`AI味严重 (${data.score}分)，建议去AI味`);
      else if (data.score >= 50) message.warning(`AI味较重 (${data.score}分)，建议润色`);
      else if (data.score >= 30) message.info(`AI味中等 (${data.score}分)`);
      else message.success(`AI味较轻 (${data.score}分)，质量不错`);
    } catch {
      message.error('检测失败');
    } finally {
      setDetectLoading(false);
    }
  };

  const handleDeAi = async () => {
    if (!id || !selectedChapter) return;
    setDeAing(true);
    setStreamContent('');
    accumulatedRef.current = '';
    try {
      await chapterApi.deAi(
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
          setAiReport(null); // 清除旧报告
        }
      );
      message.success('去AI味完成');
      fetchData();
    } catch {
      message.error('去AI味失败');
    } finally {
      setDeAing(false);
    }
  };

  /* ── 提取事件 ─────────────────────────────────────────────────── */
  const handleExtractEvents = async (ch: number) => {
    if (!id) return;
    setExtracting(true);
    setLastExtractEvents([]);
    try {
      await eventApi.triggerExtract(id, ch, (data) => {
        if (data.type === 'complete' && data.data?.events) {
          setLastExtractEvents(data.data.events);
          setLastExtractChapter(ch);
          message.success(`提取完成：${data.data.event_count} 个事件`);
        } else if (data.type === 'error') {
          message.error(data.message || '提取失败');
        }
      });
    } catch { message.error('提取请求失败'); }
    finally { setExtracting(false); }
  };

  /* ── 签署契约 ──────────────────────────────────────────────────────── */
  const handleSignContract = async (ch: number) => {
    if (!id) return;
    setSigning(true);
    try {
      const { data } = await contractApi.signContract(id, ch);
      setContract(data);
      message.success('契约签署完成');
    } catch (e: any) {
      message.error(e.message || '签署契约失败');
    } finally {
      setSigning(false);
    }
  };

  /* ── 提交章节 ──────────────────────────────────────────────────────── */
  const handleCommitChapter = async (ch: number) => {
    if (!id) return;
    setCommitting(true);
    try {
      const { data } = await contractApi.commitChapter(id, ch);
      setCommit(data);
      if (data.status === 'accepted') {
        message.success('✅ 章节提交通过');
      } else {
        message.warning('❌ 章节提交被拒绝');
      }
    } catch (e: any) {
      message.error(e.message || '提交失败');
    } finally {
      setCommitting(false);
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

  /* ── 追读力评估 ────────────────────────────────────────────────── */
  const handleEvaluateReadingPower = async (ch: number) => {
    if (!id) return;
    setEvaluating(true);
    setEvalResult(null);
    try {
      const res = await debtApi.evaluateReadingPower(id, ch);
      setEvalResult(res.data);
      if (res.data.debt_created) {
        message.warning(`追读力不足，产生债务：${res.data.debt_amount?.toFixed(1)}`);
      } else if (res.data.payment_made) {
        message.success(`偿还债务：${res.data.payment_amount?.toFixed(1)}`);
      } else {
        message.success(`评估完成：${res.data.reading_power_score} 分`);
      }
    } catch (e: any) {
      message.error(e.message || '评估失败');
    } finally {
      setEvaluating(false);
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

      {/* ── Phase 13.1：流水线进度条 ─────────────────────────────────────── */}
      {(pipelineStage || pipelineDone) && (
        <Alert
          type="info"
          showIcon
          closable
          onClose={() => { setPipelineStage(''); setPipelineDone(false); }}
          style={{ marginBottom: 16 }}
          message={pipelineDone
            ? (pipelineResult?.status === 'completed' ? '✅ 流水线全部成功' : '⚠️ 流水线完成（含错误）')
            : `🔄 流水线运行中 — ${pipelineStage}`
          }
        />
      )}

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

      {/* ── 章节契约卡片（写前） ──────────────────────────────────────────── */}
      {selectedChapter && (
        <Card
          size="small"
          style={{ marginBottom: 16, background: '#fffbe6' }}
          title={
            <Space>
              <FileTextOutlined />
              <Text strong>章节契约</Text>
              {contract && (
                <Tag color={contract.status === 'fulfilled' ? 'green' : contract.status === 'rejected' ? 'red' : contract.status === 'signed' ? 'blue' : 'default'}>
                  {CONTRACT_STATUS_LABELS[contract.status] || contract.status}
                </Tag>
              )}
            </Space>
          }
          extra={
            <Space>
              {!contract || contract.status === 'draft' ? (
                <Button
                  type="primary"
                  size="small"
                  loading={signing}
                  icon={<FileTextOutlined />}
                  onClick={() => handleSignContract(selectedChapter.chapter_number)}
                >
                  签署契约
                </Button>
              ) : contract.status === 'signed' ? (
                <Button
                  type="primary"
                  size="small"
                  loading={signing}
                  icon={<SyncOutlined />}
                  onClick={() => handleSignContract(selectedChapter.chapter_number)}
                >
                  重新签署
                </Button>
              ) : null}
            </Space>
          }
        >
          {contractLoading ? (
            <Spin size="small" />
          ) : contract ? (
            <div>
              {/* 必须覆盖的节点 */}
              <div style={{ marginBottom: 8 }}>
                <Text strong style={{ color: '#faad14' }}>📋 必须覆盖的节点：</Text>
                {contract.required_nodes.length > 0 ? (
                  <List
                    size="small"
                    dataSource={contract.required_nodes}
                    renderItem={(node) => (
                      <List.Item style={{ padding: '4px 0' }}>
                        <Space>
                          <Tag color="blue">{node.title}</Tag>
                          {node.character && (
                            <Tag color="purple">{node.character}</Tag>
                          )}
                          <Text type="secondary" style={{ fontSize: 12 }}>
                            {node.description}
                          </Text>
                        </Space>
                      </List.Item>
                    )}
                  />
                ) : (
                  <Text type="secondary" style={{ fontSize: 12, marginLeft: 8 }}>
                    无
                  </Text>
                )}
              </div>

              {/* 可选节点 */}
              {contract.optional_nodes.length > 0 && (
                <div style={{ marginBottom: 8 }}>
                  <Text strong style={{ color: '#8c8c8c' }}>📌 可选节点：</Text>
                  <List
                    size="small"
                    dataSource={contract.optional_nodes}
                    renderItem={(node) => (
                      <List.Item style={{ padding: '4px 0' }}>
                        <Tag>{node.title}</Tag>
                        {node.description && (
                          <Text type="secondary" style={{ fontSize: 12 }}>
                            {node.description}
                          </Text>
                        )}
                      </List.Item>
                    )}
                  />
                </div>
              )}

              {/* 约束 */}
              {contract.constraints.length > 0 && (
                <div style={{ marginBottom: 8 }}>
                  <Text strong style={{ color: '#8c8c8c' }}>📏 约束：</Text>
                  <Space size={4} wrap>
                    {contract.constraints.map((c, i) => (
                      <Tag key={i} color="geekblue">{c.label}: {c.value}</Tag>
                    ))}
                  </Space>
                </div>
              )}

              {/* 禁区 */}
              {contract.forbidden_zones.length > 0 && (
                <div>
                  <Text strong style={{ color: '#ff4d4f' }}>🚫 禁区：</Text>
                  <List
                    size="small"
                    dataSource={contract.forbidden_zones}
                    renderItem={(zone) => (
                      <List.Item style={{ padding: '4px 0' }}>
                        <Text type="danger" style={{ fontSize: 12 }}>
                          {zone.description}
                        </Text>
                        {zone.reason && (
                          <Text type="secondary" style={{ fontSize: 11, marginLeft: 8 }}>
                            （{zone.reason}）
                          </Text>
                        )}
                      </List.Item>
                    )}
                  />
                </div>
              )}

              {contract.context_summary && (
                <Paragraph
                  type="secondary"
                  style={{ fontSize: 11, marginTop: 8, marginBottom: 0 }}
                  italic
                >
                  上下文：{contract.context_summary}
                </Paragraph>
              )}
            </div>
          ) : (
            <Text type="secondary">
              该章节尚未签署契约。点击上方「签署契约」根据细纲自动生成写作契约。
            </Text>
          )}
        </Card>
      )}

      <div style={{ display: 'flex', gap: 16 }}>
        {/* 左侧章节列表 */}
        <Card
          title={
            <Space>
              <Text strong>章节目录</Text>
              <Tag color="cyan" style={{ cursor: 'pointer' }} onClick={handleResetFilter}>&lt;</Tag>
            </Space>
          }
          style={{ width: 320, flexShrink: 0 }}
          extra={
            <Space>
              <Text type="secondary">{chapters.length} 章</Text>
            </Space>
          }
        >
          {loading ? (
            <Spin />
          ) : chapters.length === 0 ? (
            <Empty description="暂无章节" />
          ) : (
            <>
              {/* 筛选栏：按分组 / 按标签 */}
              <div style={{ padding: '4px 0 8px', borderBottom: '1px solid #f0f0f0', marginBottom: 8 }}>
                <Space direction="vertical" style={{ width: '100%' }} size={4}>
                  <div>
                    <Text type="secondary" style={{ fontSize: 11 }}>按分组筛选</Text>
                    <Select
                      size="small"
                      placeholder="选择分组"
                      allowClear
                      showSearch
                      style={{ width: '100%', marginTop: 4 }}
                      value={groupFilter}
                      onChange={setGroupFilter}
                      options={[{ label: '（未分组）', value: '' }, ...groupKeys.map(k => ({ label: k, value: k }))]}
                    />
                  </div>
                  <div>
                    <Text type="secondary" style={{ fontSize: 11 }}>按标签筛选</Text>
                    <Select
                      size="small"
                      placeholder="选择标签"
                      allowClear
                      style={{ width: '100%', marginTop: 4 }}
                      value={tagFilter}
                      onChange={setTagFilter}
                      options={allTags.map(t => ({ label: t, value: t }))}
                    />
                  </div>
                </Space>
              </div>

              {/* 章节树：无分组置顶，有分组的按组折叠 */}
              <div>
                {/* 未分组章节 */}
                {groupedChapters['__ungrouped__']?.length && (
                  <div>
                    <div
                      style={{ fontSize: 12, color: '#8c8c8c', padding: '4px 0', display: 'flex', alignItems: 'center', gap: 4 }}
                    >
                      <Text type="secondary">📄 未分组</Text>
                      <Text type="secondary" style={{ fontSize: 11 }}>{groupedChapters['__ungrouped__'].length}</Text>
                    </div>
                    {getFilteredChapters(groupedChapters['__ungrouped__']).map(ch => (
                      <ChapterRow key={ch.id} ch={ch} />
                    ))}
                  </div>
                )}
                {/* 有分组的章节：可折叠 */}
                {groupKeys.map(key => {
                  const members = getFilteredChapters(groupedChapters[key]);
                  const collapsed = collapsedGroups[key];
                  return (
                    <div key={key} style={{ marginTop: 6 }}>
                      <div
                        style={{ fontSize: 12, padding: '4px 0', display: 'flex', alignItems: 'center', gap: 4, cursor: 'pointer', color: '#1890ff', fontWeight: 600 }}
                        onClick={() => toggleGroup(key)}
                      >
                        <Text>{collapsed ? '▶' : '▼'}</Text>
                        <FolderOutlined />
                        <Text strong>{key}</Text>
                        <Text type="secondary" style={{ fontSize: 11 }}>{members.length}</Text>
                      </div>
                      {!collapsed && members.map(ch => (
                        <ChapterRow key={ch.id} ch={ch} />
                      ))}
                    </div>
                  );
                })}
              </div>
            </>
          )}
        </Card>

        {/* 右侧写作区 */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* AI 伴侣按钮 */}
          <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
            <Button
              type={companionOpen ? 'primary' : 'default'}
              icon={<RobotOutlined />}
              onClick={() => setCompanionOpen(!companionOpen)}
            >
              {companionOpen ? '关闭 AI 伴侣' : 'AI 写作伴侣'}
            </Button>
          </div>
          {/* 流式生成区域 */}
          {streamContent && (
            <Card
              title={generating ? "正在生成..." : deAing ? "正在去AI味..." : "生成完成"}
              ref={streamRef}
              style={{ maxHeight: 300, overflow: 'auto', background: generating ? '#f6ffed' : deAing ? '#fff7e6' : '#fff' }}
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
              {/* AI味检测报告 */}
              {aiReport && (
                <Alert
                  type={aiReport.score >= 70 ? 'error' : aiReport.score >= 50 ? 'warning' : aiReport.score >= 30 ? 'info' : 'success'}
                  style={{ marginBottom: 16 }}
                  message={
                    <Space>
                      <Text strong>AI味评分：{aiReport.score}</Text>
                      <Tag color={aiReport.score >= 70 ? 'red' : aiReport.score >= 50 ? 'orange' : aiReport.score >= 30 ? 'blue' : 'green'}>
                        {aiReport.level === 'severe' ? '严重' : aiReport.level === 'high' ? '较重' : aiReport.level === 'medium' ? '中等' : '较轻'}
                      </Tag>
                      <Text type="secondary">八股词 {aiReport.stats.cliche_count} 处 · 问题 {aiReport.stats.issue_count} 项</Text>
                    </Space>
                  }
                  description={
                    aiReport.issues.length > 0 ? (
                      <div style={{ maxHeight: 200, overflow: 'auto' }}>
                        {aiReport.issues.slice(0, 15).map((issue, idx) => (
                          <div key={idx} style={{ marginBottom: 4 }}>
                            <Tag color={issue.severity === 'severe' ? 'red' : issue.severity === 'medium' ? 'orange' : 'default'}>{issue.severity}</Tag>
                            <Text code>{issue.text}</Text>
                            {issue.line > 0 && <Text type="secondary"> 行{issue.line}</Text>}
                            <Text type="secondary"> — {issue.suggestion}</Text>
                          </div>
                        ))}
                        {aiReport.issues.length > 15 && <Text type="secondary">...还有 {aiReport.issues.length - 15} 项</Text>}
                      </div>
                    ) : <Text type="secondary">未发现明显AI痕迹</Text>
                  }
                  closable
                  onClose={() => setAiReport(null)}
                />
              )}

              <TiptapEditor
                value={editingContent}
                onChange={(text) => setEditingContent(text)}
                height={500}
              />
              <div style={{ textAlign: 'right', marginTop: 12 }}>
                <Space>
                  <Button
                    icon={<ExperimentOutlined />}
                    loading={detectLoading}
                    disabled={deAing || regenerating}
                    onClick={handleDetectAi}
                  >
                    检测AI味
                  </Button>
                  {aiReport && aiReport.score >= 30 && (
                    <Popconfirm
                      title="确认去AI味改写？"
                      description="AI将改写本章内容以降低AI痕迹，改写后可手动调整。"
                      onConfirm={handleDeAi}
                      okText="确认改写"
                      cancelText="取消"
                    >
                      <Button
                        type="primary"
                        icon={<MedicineBoxOutlined />}
                        loading={deAing}
                        disabled={saving || regenerating}
                        danger={aiReport.score >= 70}
                      >
                        去AI味
                      </Button>
                    </Popconfirm>
                  )}
                  <Popconfirm
                    title="确认重新生成此章节？"
                    description="已编辑的内容将被替换为 AI 重新生成的内容，且无法恢复。"
                    onConfirm={handleRegenerate}
                    okText="确认重新生成"
                    cancelText="取消"
                    okButtonProps={{ danger: true }}
                  >
                    <Button icon={<ThunderboltOutlined />} loading={regenerating} disabled={saving || deAing}>
                      重新生成
                    </Button>
                  </Popconfirm>
                  <Button type="primary" icon={<SendOutlined />} loading={saving} disabled={regenerating || deAing} onClick={() => handleSave()}>保存</Button>
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

      {companionOpen && selectedChapter && (
        <WritingCompanionPanel
          projectId={id!}
          projectName={selectedChapter.title || '未命名'}
          chapterNumber={selectedChapter.chapter_number}
          recentText={editingContent}
          previousContext={previousSummary || ''}
          worldview={''}
          characterList={''}
          onClose={() => setCompanionOpen(false)}
          onInsert={(text) => {
            setEditingContent(prev => prev + '\n\n' + text);
            message.info('已插入续写建议到编辑器末尾');
          }}
        />
      )}

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
      {/* ── 提取事件面板（折叠式） ─────────────────────────────────── */}
      <Collapse
        style={{ marginTop: 16, background: '#fafafa' }}
        items={[{
          key: 'extract-events',
          label: (
            <Space>
              <ThunderboltOutlined />
              <Text strong>提取事件</Text>
              {lastExtractEvents.length > 0 && (
                <Text type="secondary">上次提取 {lastExtractEvents.length} 个事件（第{lastExtractChapter}章）</Text>
              )}
            </Space>
          ),
          children: (
            <Space direction="vertical" size="middle" style={{ width: '100%' }}>
              <Space>
                <Text>目标章节：</Text>
                <InputNumber
                  min={1}
                  value={selectedChapter?.chapter_number || 1}
                  onChange={(v) => v !== null && setSelectedChapterNum(v)}
                />
                <Button type="primary" loading={extracting} icon={<ThunderboltOutlined />}
                        onClick={() => handleExtractEvents(selectedChapter?.chapter_number || 1)}>
                  提取事件
                </Button>
              </Space>
              {lastExtractEvents.length > 0 && (
                <List size="small" dataSource={lastExtractEvents}
                      renderItem={(ev) => (
                        <List.Item>
                          <Tag color="#1890ff">{ev.event_type_label}</Tag>
                          <Text>{ev.title}</Text>
                        </List.Item>
                      )} />
              )}
            </Space>
          ),
        }]}
      />
      {/* ── 追读力评估面板（折叠式） ─────────────────────────────────── */}
      <Collapse
        style={{ marginTop: 16, background: '#fafafa' }}
        items={[{
          key: 'reading-power',
          label: (
            <Space>
              <BarChartOutlined />
              <Text strong>追读力评估</Text>
              {evalResult && (
                <Text type="secondary">
                  {evalResult.reading_power_score} 分
                  {evalResult.debt_created && ' 💸 欠债'}
                  {evalResult.payment_made && ' ✅ 偿还'}
                </Text>
              )}
            </Space>
          ),
          children: (
            <Space direction="vertical" size="middle" style={{ width: '100%' }}>
              <Space>
                <Text>目标章节：</Text>
                <InputNumber
                  min={1}
                  value={evalChapterNum}
                  onChange={(v) => setEvalChapterNum(v || 1)}
                />
                <Button type="primary" loading={evaluating} icon={<BarChartOutlined />}
                        onClick={() => handleEvaluateReadingPower(evalChapterNum)}>
                  评估追读力
                </Button>
              </Space>
              {evalResult && (
                <Card size="small" style={{ background: '#f5f5f5' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                    <tbody>
                      <tr>
                        <td style={{ padding: '4px 12px', whiteSpace: 'nowrap', color: '#888' }}>追读力评分</td>
                        <td style={{ padding: '4px 12px' }}>
                          <Text strong style={{ color: SCORE_COLOR(evalResult.reading_power_score) }}>
                            {evalResult.reading_power_score}
                          </Text>
                        </td>
                        <td style={{ padding: '4px 12px', whiteSpace: 'nowrap', color: '#888' }}>钩子类型</td>
                        <td style={{ padding: '4px 12px' }}>{HOOK_TYPE_LABELS[evalResult.hook_type] || evalResult.hook_type}</td>
                      </tr>
                      <tr>
                        <td style={{ padding: '4px 12px', whiteSpace: 'nowrap', color: '#888' }}>钩子强度</td>
                        <td style={{ padding: '4px 12px' }}>
                          <Tag color={evalResult.hook_strength === 'strong' ? 'green' :
                                evalResult.hook_strength === 'medium' ? 'blue' : 'red'}>
                            {HOOK_STRENGTH_LABELS[evalResult.hook_strength] || evalResult.hook_strength}
                          </Tag>
                        </td>
                        <td style={{ padding: '4px 12px', whiteSpace: 'nowrap', color: '#888' }}>过渡章</td>
                        <td style={{ padding: '4px 12px' }}>{evalResult.is_transition ? '✅ 是' : '❌ 否'}</td>
                      </tr>
                      <tr>
                        <td style={{ padding: '4px 12px', whiteSpace: 'nowrap', color: '#888' }}>钩子描述</td>
                        <td style={{ padding: '4px 12px' }} colSpan={3}>{evalResult.hook_description || '无'}</td>
                      </tr>
                      <tr>
                        <td style={{ padding: '4px 12px', whiteSpace: 'nowrap', color: '#888' }}>爽点模式</td>
                        <td style={{ padding: '4px 12px' }} colSpan={3}>
                          {(evalResult.coolpoint_patterns || []).length > 0
                            ? evalResult.coolpoint_patterns.map((p, i) => <Tag key={i}>{p}</Tag>)
                            : <Text type="secondary">无</Text>}
                        </td>
                      </tr>
                      <tr>
                        <td style={{ padding: '4px 12px', whiteSpace: 'nowrap', color: '#888' }}>微兑现</td>
                        <td style={{ padding: '4px 12px' }} colSpan={3}>
                          {(evalResult.micropayoffs || []).length > 0
                            ? evalResult.micropayoffs.map((p, i) => <Tag key={i}>{p}</Tag>)
                            : <Text type="secondary">无</Text>}
                        </td>
                      </tr>
                    </tbody>
                  </table>
                  {evalResult.debt_created && (
                    <Alert type="warning" showIcon style={{ marginTop: 8 }}
                      message={`产生债务：${DEBT_TYPE_LABELS[evalResult.hook_type] || '追读力'} (${evalResult.debt_amount?.toFixed(1)})`} />
                  )}
                  {evalResult.payment_made && (
                    <Alert type="success" showIcon style={{ marginTop: 8 }}
                      message={`偿还债务：${evalResult.payment_amount?.toFixed(1)}`} />
                  )}
                </Card>
              )}
            </Space>
          ),
        }]}
      />
      {/* ── 提交结果面板（写后） ─────────────────────────────────────────── */}
      <Collapse
        style={{ marginTop: 16, background: '#fafafa' }}
        items={[{
          key: 'chapter-commit',
          label: (
            <Space>
              <SendOutlined />
              <Text strong>提交结果</Text>
              {commit && (
                <Text type="secondary">
                  {COMMIT_STATUS_LABELS[commit.status] || commit.status}
                  {' · '}v{commit.commit_version}
                  {commit.status === 'rejected' && (
                    <Text type="danger"> · {commit.rejection_reasons.length} 个问题</Text>
                  )}
                </Text>
              )}
            </Space>
          ),
          children: (
            <Space direction="vertical" size="middle" style={{ width: '100%' }}>
              <Space>
                <Text>目标章节：</Text>
                <InputNumber
                  min={1}
                  value={selectedChapter?.chapter_number || 1}
                  onChange={(v) => v !== null && setSelectedChapterNum(v)}
                />
                <Button
                  type="primary"
                  loading={committing}
                  icon={<SendOutlined />}
                  onClick={() => handleCommitChapter(selectedChapter?.chapter_number || 1)}
                >
                  提交章节
                </Button>
              </Space>

              {commitLoading ? (
                <Spin />
              ) : commit ? (
                <Card size="small" style={{ background: '#f5f5f5' }}>
                  {/* 判定结果 */}
                  <Alert
                    type={commit.status === 'accepted' ? 'success' : 'error'}
                    showIcon
                    style={{ marginBottom: 12 }}
                    message={
                      <Space>
                        <Text strong>
                          {commit.status === 'accepted' ? '✅ 提交通过' : '❌ 提交被拒绝'}
                        </Text>
                        <Tag>v{commit.commit_version}</Tag>
                      </Space>
                    }
                    description={
                      commit.rejection_reasons.length > 0 ? (
                        <ul style={{ margin: 0, paddingLeft: 20 }}>
                          {commit.rejection_reasons.map((r, i) => (
                            <li key={i}><Text type="danger">{r}</Text></li>
                          ))}
                        </ul>
                      ) : commit.status === 'accepted' ? (
                        <Text type="success">所有检查通过，无阻断问题和缺失节点。</Text>
                      ) : null
                    }
                  />

                  {/* 履行结果 */}
                  {commit.fulfillment_result && (
                    <div style={{ marginBottom: 12 }}>
                      <Text strong style={{ color: '#722ed1' }}>📋 履行结果</Text>
                      <div style={{ marginTop: 4 }}>
                        <Space wrap>
                          <Text>
                            覆盖节点：
                            <Text strong style={{ color: '#52c41a' }}>
                              {commit.fulfillment_result.covered_nodes?.length || 0}
                            </Text>
                            /{commit.fulfillment_result.planned_nodes?.length || 0}
                          </Text>
                          {commit.fulfillment_result.missed_nodes?.length > 0 && (
                            <Text type="danger">
                              缺失：{commit.fulfillment_result.missed_nodes.length} 个
                            </Text>
                          )}
                          {commit.fulfillment_result.extra_nodes?.length > 0 && (
                            <Text type="secondary">
                              额外：{commit.fulfillment_result.extra_nodes.length} 个
                            </Text>
                          )}
                          {commit.fulfillment_result.forbidden_violations?.length > 0 && (
                            <Text type="danger">
                              触犯禁区：{commit.fulfillment_result.forbidden_violations.length} 处
                            </Text>
                          )}
                        </Space>
                        {commit.fulfillment_result.summary && (
                          <Paragraph
                            type="secondary"
                            style={{ fontSize: 12, marginTop: 4, marginBottom: 0 }}
                            italic
                          >
                            {commit.fulfillment_result.summary}
                          </Paragraph>
                        )}
                      </div>
                    </div>
                  )}

                  {/* 审查结果 */}
                  {commit.review_result && (
                    <div style={{ marginBottom: 12 }}>
                      <Text strong style={{ color: '#1890ff' }}>🔍 审查结果</Text>
                      <div style={{ marginTop: 4 }}>
                        <Space wrap>
                          {commit.review_result.overall_score !== null && (
                            <Text>
                              评分：
                              <Text strong style={{ color: '#1890ff' }}>
                                {commit.review_result.overall_score}
                              </Text>
                            </Text>
                          )}
                          <Text>
                            阻断问题：
                            <Text strong style={{ color: commit.review_result.blocking_count > 0 ? '#ff4d4f' : '#52c41a' }}>
                              {commit.review_result.blocking_count}
                            </Text>
                          </Text>
                        </Space>
                        {commit.review_result.blocking_issues?.length > 0 && (
                          <ul style={{ margin: '4px 0 0', paddingLeft: 20 }}>
                            {commit.review_result.blocking_issues.map((issue, i) => (
                              <li key={i}><Text type="danger" style={{ fontSize: 12 }}>{issue}</Text></li>
                            ))}
                          </ul>
                        )}
                      </div>
                    </div>
                  )}

                  {/* 提取结果 */}
                  {commit.extraction_result && (
                    <div>
                      <Text strong style={{ color: '#13c2c2' }}>⚡ 事件提取</Text>
                      <div style={{ marginTop: 4 }}>
                        <Text>
                          提取事件：
                          <Text strong>{commit.extraction_result.event_count}</Text> 个
                          {commit.extraction_result.event_types?.length > 0 && (
                            <Space size={4} style={{ marginLeft: 8 }}>
                              {commit.extraction_result.event_types.map((t, i) => (
                                <Tag key={i} style={{ fontSize: 11 }}>{EVENT_TYPE_LABELS[t] || t}</Tag>
                              ))}
                            </Space>
                          )}
                        </Text>
                      </div>
                    </div>
                  )}
                </Card>
              ) : (
                <Text type="secondary">
                  该章节尚未提交。点击「提交章节」进行审查+履行检查+事件提取的汇总判定。
                </Text>
              )}
            </Space>
          ),
        }]}
      />
    </AppLayout>
  );

  // ── 章节行（嵌套组件，捕获父级闭包：选中态、删除、分组、标签） ────
  function ChapterRow({ ch }: { ch: Chapter }) {
    const [localGroup, setLocalGroup] = useState(ch.group || '');
    const [localTag, setLocalTag] = useState('');
    return (
      <div
        onClick={() => handleSelectChapter(ch)}
        style={{
          cursor: 'pointer',
          padding: '6px 8px',
          marginBottom: 2,
          borderRadius: 4,
          background: selectedChapter?.id === ch.id ? '#e6f4ff' : undefined,
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <Text strong style={{ fontSize: 13 }}>
            {ch.title?.startsWith('第') ? ch.title : `第${ch.chapter_number}章 ${ch.title}`}
          </Text>
          <Popconfirm
            title={`确认删除第${ch.chapter_number}章？`}
            onConfirm={() => handleDelete(ch)}
            okText="确认"
            cancelText="取消"
          >
            <Button
              type="text"
              size="small"
              danger
              icon={<DeleteOutlined />}
              style={{ padding: '0 4px' }}
              onClick={(e) => e.stopPropagation()}
            />
          </Popconfirm>
        </div>
        <div style={{ fontSize: 12, marginTop: 2, display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
          <Tag>{ch.status}</Tag>
          <Text type="secondary">{ch.word_count}字</Text>
        </div>
        {/* 分组 + 标签行 */}
        <div style={{ marginTop: 4, display: 'flex', alignItems: 'center', gap: 4, flexWrap: 'wrap' }}>
          <Select
            size="small"
            placeholder="分组"
            allowClear
            value={localGroup}
            onChange={(v) => { setLocalGroup(v); handleSetGroup(ch, v || null); }}
            style={{ width: 90 }}
            onClick={(e) => e.stopPropagation()}
            suffixIcon={<FolderOutlined />}
            options={groupKeys.map(k => ({ label: k, value: k }))}
          />
          {/* 标签 chips */}
          {(ch.tags || []).map((t, i) => (
            <Tag
              key={i}
              closable
              onClose={() => { const e = null; e; handleRemoveTag(ch, t); }}
              style={{ fontSize: 11, cursor: 'pointer' }}
              onClick={(e) => e.stopPropagation()}
            >
              {t}
            </Tag>
          ))}
          {/* 添加标签 */}
          <div
            style={{ display: 'flex', alignItems: 'center', gap: 2 }}
            onClick={(e) => e.stopPropagation()}
          >
            <Input
              size="small"
              placeholder="标签+"
              value={localTag}
              onChange={(e) => setLocalTag(e.target.value)}
              onPressEnter={() => { handleAddTag(ch, localTag); setLocalTag(''); }}
              style={{ width: 60 }}
            />
            <Button size="small" type="text" icon={<PlusOutlined />} onClick={() => { handleAddTag(ch, localTag); setLocalTag(''); }} />
          </div>
        </div>
      </div>
    );
  }
}
