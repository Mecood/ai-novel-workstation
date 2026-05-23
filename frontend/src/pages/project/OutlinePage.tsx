import { useParams } from 'react-router-dom';
import { useEffect, useMemo, useState, useCallback } from 'react';
import {
  Card,
  Typography,
  Button,
  List,
  Input,
  Empty,
  Spin,
  message,
  Space,
  Tag,
  Collapse,
  Modal,
  Form,
  InputNumber,
  Popconfirm,
  Row,
  Col,
  Divider,
} from 'antd';
import {
  OrderedListOutlined,
  SaveOutlined,
  ReloadOutlined,
  PlusOutlined,
  ThunderboltOutlined,
  DeleteOutlined,
  BookOutlined,
} from '@ant-design/icons';
import AppLayout from '../../components/layout/AppLayout';
import { chapterApi, volumeApi } from '../../services/api';
import type { Chapter, Volume, ChapterOutlineDetail } from '../../services/api';

const { Title, Paragraph, Text } = Typography;
const { TextArea } = Input;

interface VolumeDraft extends Volume {
  draftTitle: string;
  draftDescription: string;
  draftChapterStart: number;
  draftChapterEnd: number | null;
  draftHighlightRhythm: string;
  draftEmotionArc: string;
  draftForeshadowingNotes: string;
  draftTwists: string;
}

interface ChapterDraft extends Chapter {
  draftSummary: string;
  draftEvents: string;
  draftHooks: string;
  draftHighlights: string;
  draftSuspense: string;
}

const toStr = (v: unknown): string => {
  if (v == null) return '';
  if (typeof v === 'string') return v;
  try {
    return JSON.stringify(v, null, 2);
  } catch {
    return String(v);
  }
};

const buildVolumeDraft = (v: Volume): VolumeDraft => ({
  ...v,
  draftTitle: v.title || '',
  draftDescription: v.description || '',
  draftChapterStart: v.chapter_start ?? 1,
  draftChapterEnd: v.chapter_end ?? null,
  draftHighlightRhythm: toStr(v.highlight_rhythm),
  draftEmotionArc: toStr(v.emotion_arc),
  draftForeshadowingNotes: toStr(v.foreshadowing_notes),
  draftTwists: toStr(v.twists),
});

const buildChapterDraft = (c: Chapter): ChapterDraft => {
  const o = (c.outline_detail || {}) as ChapterOutlineDetail;
  return {
    ...c,
    draftSummary: c.summary || '',
    draftEvents: o.events || '',
    draftHooks: o.hooks || '',
    draftHighlights: o.highlights || '',
    draftSuspense: o.suspense || '',
  };
};

export default function OutlinePage() {
  const { id } = useParams<{ id: string }>();
  const [volumes, setVolumes] = useState<VolumeDraft[]>([]);
  const [chapters, setChapters] = useState<ChapterDraft[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [createForm] = Form.useForm();
  const [activeKeys, setActiveKeys] = useState<string[]>([]);

  const fetchData = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    try {
      const [vRes, cRes] = await Promise.all([
        volumeApi.list(id),
        chapterApi.list(id),
      ]);
      const vList = Array.isArray(vRes.data) ? vRes.data : [];
      const cList = Array.isArray(cRes.data) ? cRes.data : [];
      const vSorted = [...vList].sort((a, b) => a.volume_number - b.volume_number);
      const cSorted = [...cList].sort((a, b) => a.chapter_number - b.chapter_number);
      setVolumes(vSorted.map(buildVolumeDraft));
      setChapters(cSorted.map(buildChapterDraft));
    } catch {
      message.error('加载大纲失败');
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const chaptersByVolume = useMemo(() => {
    const map = new Map<string, ChapterDraft[]>();
    for (const vol of volumes) {
      const start = vol.draftChapterStart ?? 1;
      const end = vol.draftChapterEnd ?? Number.MAX_SAFE_INTEGER;
      const list = chapters.filter(
        (c) => c.chapter_number >= start && c.chapter_number <= end,
      );
      map.set(vol.id, list);
    }
    return map;
  }, [volumes, chapters]);

  const unassignedChapters = useMemo(() => {
    if (volumes.length === 0) return chapters;
    return chapters.filter((c) => {
      return !volumes.some((v) => {
        const start = v.draftChapterStart ?? 1;
        const end = v.draftChapterEnd ?? Number.MAX_SAFE_INTEGER;
        return c.chapter_number >= start && c.chapter_number <= end;
      });
    });
  }, [volumes, chapters]);

  const updateVolumeField = <K extends keyof VolumeDraft>(
    volumeId: string,
    field: K,
    value: VolumeDraft[K],
  ) => {
    setVolumes((prev) =>
      prev.map((v) => (v.id === volumeId ? { ...v, [field]: value } : v)),
    );
  };

  const updateChapterField = <K extends keyof ChapterDraft>(
    chapterId: string,
    field: K,
    value: ChapterDraft[K],
  ) => {
    setChapters((prev) =>
      prev.map((c) => (c.id === chapterId ? { ...c, [field]: value } : c)),
    );
  };

  const handleCreateVolume = async () => {
    if (!id) return;
    try {
      const values = await createForm.validateFields();
      const { data } = await volumeApi.create(id, {
        title: values.title,
        description: values.description,
        chapter_start: values.chapter_start ?? 1,
        chapter_end: values.chapter_end ?? null,
      });
      setVolumes((prev) => [...prev, buildVolumeDraft(data)]);
      setActiveKeys((prev) => [...prev, data.id]);
      message.success('已创建新卷');
      setCreateOpen(false);
      createForm.resetFields();
    } catch (e: any) {
      if (e?.errorFields) return;
      message.error('创建卷失败');
    }
  };

  const handleDeleteVolume = async (volumeId: string) => {
    if (!id) return;
    try {
      await volumeApi.delete(id, volumeId);
      setVolumes((prev) => prev.filter((v) => v.id !== volumeId));
      message.success('已删除');
    } catch {
      message.error('删除失败');
    }
  };

  const handleSaveAll = async () => {
    if (!id) return;
    setSaving(true);
    message.loading({ content: '保存中...', key: 'outline_save' });
    try {
      await Promise.all(
        volumes.map((v) =>
          volumeApi.update(id, v.id, {
            title: v.draftTitle,
            description: v.draftDescription || null,
            chapter_start: v.draftChapterStart,
            chapter_end: v.draftChapterEnd,
            highlight_rhythm: v.draftHighlightRhythm || null,
            emotion_arc: v.draftEmotionArc || null,
            foreshadowing_notes: v.draftForeshadowingNotes || null,
            twists: v.draftTwists || null,
          }),
        ),
      );
      await Promise.all(
        chapters.map((c) =>
          chapterApi.update(id, c.id, {
            title: c.title,
            summary: c.draftSummary,
            status: c.status,
            outline_detail: {
              events: c.draftEvents,
              hooks: c.draftHooks,
              highlights: c.draftHighlights,
              suspense: c.draftSuspense,
            },
          }),
        ),
      );
      message.success({ content: '大纲已保存', key: 'outline_save' });
    } catch {
      message.error({ content: '保存失败', key: 'outline_save' });
    } finally {
      setSaving(false);
    }
  };

  const renderChapterItem = (chapter: ChapterDraft) => (
    <List.Item
      key={chapter.id}
      style={{
        padding: '12px 16px',
        background: '#fafafa',
        borderRadius: 8,
        marginBottom: 8,
      }}
    >
      <div style={{ width: '100%' }}>
        <Space size={8} style={{ marginBottom: 8 }} wrap>
          <Text strong>第 {chapter.chapter_number} 章</Text>
          <Text>{chapter.title || '未命名章节'}</Text>
          <Tag color="blue">{chapter.status}</Tag>
          <Text type="secondary">{chapter.word_count} 字</Text>
        </Space>
        <TextArea
          value={chapter.draftSummary}
          onChange={(e) => updateChapterField(chapter.id, 'draftSummary', e.target.value)}
          placeholder="本章简介 / 摘要"
          autoSize={{ minRows: 2, maxRows: 4 }}
          style={{ marginBottom: 8 }}
        />
        <Row gutter={[12, 8]}>
          <Col xs={24} md={12}>
            <Text type="secondary" style={{ fontSize: 12 }}>事件</Text>
            <TextArea
              value={chapter.draftEvents}
              onChange={(e) => updateChapterField(chapter.id, 'draftEvents', e.target.value)}
              placeholder="本章发生的关键事件、场景变化"
              autoSize={{ minRows: 2, maxRows: 5 }}
            />
          </Col>
          <Col xs={24} md={12}>
            <Text type="secondary" style={{ fontSize: 12 }}>钩子</Text>
            <TextArea
              value={chapter.draftHooks}
              onChange={(e) => updateChapterField(chapter.id, 'draftHooks', e.target.value)}
              placeholder="章节开篇 / 结尾的钩子"
              autoSize={{ minRows: 2, maxRows: 5 }}
            />
          </Col>
          <Col xs={24} md={12}>
            <Text type="secondary" style={{ fontSize: 12 }}>爽点</Text>
            <TextArea
              value={chapter.draftHighlights}
              onChange={(e) => updateChapterField(chapter.id, 'draftHighlights', e.target.value)}
              placeholder="情绪高潮 / 爽点设计"
              autoSize={{ minRows: 2, maxRows: 5 }}
            />
          </Col>
          <Col xs={24} md={12}>
            <Text type="secondary" style={{ fontSize: 12 }}>悬念</Text>
            <TextArea
              value={chapter.draftSuspense}
              onChange={(e) => updateChapterField(chapter.id, 'draftSuspense', e.target.value)}
              placeholder="埋下的悬念 / 未解之谜"
              autoSize={{ minRows: 2, maxRows: 5 }}
            />
          </Col>
        </Row>
      </div>
    </List.Item>
  );

  const volumeHeader = (v: VolumeDraft) => {
    const rangeText =
      v.draftChapterEnd != null
        ? `第 ${v.draftChapterStart}-${v.draftChapterEnd} 章`
        : `第 ${v.draftChapterStart} 章 起`;
    return (
      <Space size={8} wrap>
        <BookOutlined style={{ color: '#1677ff' }} />
        <Text strong>卷 {v.volume_number}</Text>
        <Text>{v.draftTitle || '未命名'}</Text>
        <Tag color="geekblue">{rangeText}</Tag>
      </Space>
    );
  };

  const renderVolumeBody = (v: VolumeDraft) => {
    const list = chaptersByVolume.get(v.id) || [];
    return (
      <div>
        <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
          <Col xs={24} md={12}>
            <Text type="secondary" style={{ fontSize: 12 }}>卷名</Text>
            <Input
              value={v.draftTitle}
              onChange={(e) => updateVolumeField(v.id, 'draftTitle', e.target.value)}
              placeholder="本卷标题"
            />
          </Col>
          <Col xs={12} md={6}>
            <Text type="secondary" style={{ fontSize: 12 }}>起始章节</Text>
            <InputNumber
              value={v.draftChapterStart}
              min={1}
              style={{ width: '100%' }}
              onChange={(value) =>
                updateVolumeField(v.id, 'draftChapterStart', Number(value) || 1)
              }
            />
          </Col>
          <Col xs={12} md={6}>
            <Text type="secondary" style={{ fontSize: 12 }}>结束章节</Text>
            <InputNumber
              value={v.draftChapterEnd ?? undefined}
              min={v.draftChapterStart}
              placeholder="可留空"
              style={{ width: '100%' }}
              onChange={(value) =>
                updateVolumeField(
                  v.id,
                  'draftChapterEnd',
                  value == null ? null : Number(value),
                )
              }
            />
          </Col>
          <Col span={24}>
            <Text type="secondary" style={{ fontSize: 12 }}>本卷描述</Text>
            <TextArea
              value={v.draftDescription}
              onChange={(e) => updateVolumeField(v.id, 'draftDescription', e.target.value)}
              placeholder="本卷的故事主线、核心命题"
              autoSize={{ minRows: 2, maxRows: 5 }}
            />
          </Col>
          <Col xs={24} md={12}>
            <Text type="secondary" style={{ fontSize: 12 }}>爽点节奏</Text>
            <TextArea
              value={v.draftHighlightRhythm}
              onChange={(e) => updateVolumeField(v.id, 'draftHighlightRhythm', e.target.value)}
              placeholder="本卷的爽点分布与节奏，例如：第3章打脸 / 第7章拿到新身份"
              autoSize={{ minRows: 3, maxRows: 6 }}
            />
          </Col>
          <Col xs={24} md={12}>
            <Text type="secondary" style={{ fontSize: 12 }}>情绪弧线</Text>
            <TextArea
              value={v.draftEmotionArc}
              onChange={(e) => updateVolumeField(v.id, 'draftEmotionArc', e.target.value)}
              placeholder="本卷情绪起伏：压抑→爆发→反思……"
              autoSize={{ minRows: 3, maxRows: 6 }}
            />
          </Col>
          <Col xs={24} md={12}>
            <Text type="secondary" style={{ fontSize: 12 }}>伏笔规划</Text>
            <TextArea
              value={v.draftForeshadowingNotes}
              onChange={(e) =>
                updateVolumeField(v.id, 'draftForeshadowingNotes', e.target.value)
              }
              placeholder="本卷埋设的伏笔、需要在后续卷回收的细节"
              autoSize={{ minRows: 3, maxRows: 6 }}
            />
          </Col>
          <Col xs={24} md={12}>
            <Text type="secondary" style={{ fontSize: 12 }}>反转设计</Text>
            <TextArea
              value={v.draftTwists}
              onChange={(e) => updateVolumeField(v.id, 'draftTwists', e.target.value)}
              placeholder="关键反转、身份揭示、立场反转"
              autoSize={{ minRows: 3, maxRows: 6 }}
            />
          </Col>
        </Row>

        <Divider style={{ margin: '8px 0 16px' }}>
          <Text type="secondary" style={{ fontSize: 12 }}>
            本卷章节细纲（{list.length}）
          </Text>
        </Divider>

        {list.length === 0 ? (
          <Empty
            description="该章节范围内尚无章节"
            image={Empty.PRESENTED_IMAGE_SIMPLE}
          />
        ) : (
          <List dataSource={list} renderItem={renderChapterItem} split={false} />
        )}
      </div>
    );
  };

  return (
    <AppLayout projectId={id!}>
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
        <div>
          <Title level={3} style={{ margin: 0 }}>
            <OrderedListOutlined style={{ marginRight: 8 }} />
            卷纲 & 细纲
          </Title>
          <Paragraph type="secondary" style={{ margin: '4px 0 0' }}>
            为每一卷规划主线、爽点与伏笔，并为每个章节填写事件、钩子、爽点、悬念
          </Paragraph>
        </div>
        <Space wrap>
          <Button icon={<ReloadOutlined />} onClick={fetchData} disabled={loading}>
            刷新
          </Button>
          <Button icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
            添加卷
          </Button>
          <Button
            icon={<ThunderboltOutlined />}
            onClick={() => message.info('AI 生成大纲功能即将上线')}
          >
            AI 生成大纲
          </Button>
          <Button
            type="primary"
            icon={<SaveOutlined />}
            onClick={handleSaveAll}
            loading={saving}
            disabled={loading}
          >
            保存全部
          </Button>
        </Space>
      </div>

      {loading ? (
        <Card>
          <div style={{ textAlign: 'center', padding: 48 }}>
            <Spin />
          </div>
        </Card>
      ) : volumes.length === 0 && chapters.length === 0 ? (
        <Card>
          <Empty
            image={<OrderedListOutlined style={{ fontSize: 64, color: '#d9d9d9' }} />}
            description="暂无卷与章节，点击「添加卷」开始规划，或到「写作工作区」生成章节"
          />
        </Card>
      ) : (
        <>
          {volumes.length === 0 ? (
            <Card style={{ marginBottom: 16 }}>
              <Empty
                description="尚未规划任何卷，点击右上角「添加卷」开始"
                image={Empty.PRESENTED_IMAGE_SIMPLE}
              />
            </Card>
          ) : (
            <Collapse
              activeKey={activeKeys}
              onChange={(keys) =>
                setActiveKeys(Array.isArray(keys) ? keys : [keys as string])
              }
              items={volumes.map((v) => ({
                key: v.id,
                label: volumeHeader(v),
                extra: (
                  <Popconfirm
                    title="确定删除该卷？"
                    description="只删除卷信息，不会删除章节"
                    onConfirm={(e) => {
                      e?.stopPropagation();
                      handleDeleteVolume(v.id);
                    }}
                    onCancel={(e) => e?.stopPropagation()}
                  >
                    <Button
                      type="text"
                      size="small"
                      icon={<DeleteOutlined />}
                      onClick={(e) => e.stopPropagation()}
                      danger
                    />
                  </Popconfirm>
                ),
                children: renderVolumeBody(v),
              }))}
              style={{ background: 'transparent' }}
            />
          )}

          {unassignedChapters.length > 0 && (
            <Card
              size="small"
              title={
                <Space>
                  <Text type="secondary">未归卷的章节</Text>
                  <Tag>{unassignedChapters.length}</Tag>
                </Space>
              }
              style={{ marginTop: 16 }}
            >
              <List
                dataSource={unassignedChapters}
                renderItem={renderChapterItem}
                split={false}
              />
            </Card>
          )}
        </>
      )}

      <Modal
        title="添加新卷"
        open={createOpen}
        onCancel={() => {
          setCreateOpen(false);
          createForm.resetFields();
        }}
        onOk={handleCreateVolume}
        okText="创建"
        cancelText="取消"
      >
        <Form form={createForm} layout="vertical" initialValues={{ chapter_start: 1 }}>
          <Form.Item
            label="卷名"
            name="title"
            rules={[{ required: true, message: '请输入卷名' }]}
          >
            <Input placeholder="例如：少年崛起" />
          </Form.Item>
          <Form.Item label="本卷描述" name="description">
            <TextArea placeholder="本卷的核心命题与主线（可稍后补充）" rows={3} />
          </Form.Item>
          <Row gutter={12}>
            <Col span={12}>
              <Form.Item label="起始章节" name="chapter_start">
                <InputNumber min={1} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item label="结束章节" name="chapter_end">
                <InputNumber min={1} style={{ width: '100%' }} placeholder="可留空" />
              </Form.Item>
            </Col>
          </Row>
        </Form>
      </Modal>
    </AppLayout>
  );
}
