import { useEffect, useState, useMemo } from 'react';
import { useParams } from 'react-router-dom';
import {
  Card, Typography, Form, Select, InputNumber, Button, message,
  Spin, List, Tag, Alert, Result, Input, Collapse, Descriptions, Statistic, Row, Col,
} from 'antd';
import AppLayout from '../../components/layout/AppLayout';
import { projectApi, backupApi } from '../../services/api';
import type { Project } from '../../services/api';

const { Title, Text, Paragraph } = Typography;
const { TextArea } = Input;

interface StoryCoreSettings {
  style?: string;
  targetWords?: number;
  temperature?: number;
}

const DEFAULT_SETTINGS: StoryCoreSettings = {
  style: 'default',
  targetWords: 3000,
  temperature: 0.8,
};

interface ConsistencyConflict {
  type: string;
  severity: string;
  detail: string;
  sources: string[];
}

// ── Outline types ──────────────────────────────────────────
interface OutlineVolume {
  title: string;
  chapters_range?: string;
  chapter_count?: number;
  core_conflict?: string;
  description?: string;
}

interface OutlineRaw {
  total_target_words?: number;
  total_volumes?: number;
  total_chapters?: number;
  words_per_chapter?: number;
  style_reference?: string;
  volumes?: OutlineVolume[];
}

/** story_core / context 可能在 DB 里以 JSON 字符串存储，安全解析 */
function safeParseJSON<T>(val: unknown): T | null {
  if (val == null) return null;
  if (typeof val === 'object') return val as T;
  if (typeof val === 'string') {
    try {
      return JSON.parse(val) as T;
    } catch {
      return null;
    }
  }
  return null;
}

export default function ProjectSettingsPage() {
  const { id } = useParams<{ id: string }>();
  const [form] = Form.useForm<StoryCoreSettings>();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [checkLoading, setCheckLoading] = useState(false);
  const [checkResult, setCheckResult] = useState<{
    conflicts: ConsistencyConflict[];
    healthy: boolean;
  } | null>(null);

  // 书籍简介
  const [description, setDescription] = useState('');
  const [descSaving, setDescSaving] = useState(false);

  // 项目原始数据（含 context.outline_raw）
  const [project, setProject] = useState<Project | null>(null);

  // 解析 outline_raw
  const outline = useMemo<OutlineRaw | null>(() => {
    if (!project?.context) return null;
    const ctx = safeParseJSON<Record<string, unknown>>(project.context);
    if (!ctx) return null;
    const raw = ctx.outline_raw;
    return safeParseJSON<OutlineRaw>(raw);
  }, [project]);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    projectApi
      .get(id)
      .then((res) => {
        const proj = res.data;
        setProject(proj);
        setDescription(proj.description ?? '');

        // story_core 可能是 JSON 字符串
        const sc = safeParseJSON<StoryCoreSettings>(proj.story_core) ?? {};
        form.setFieldsValue({
          style: sc.style ?? DEFAULT_SETTINGS.style,
          targetWords: sc.targetWords ?? DEFAULT_SETTINGS.targetWords,
          temperature: sc.temperature ?? DEFAULT_SETTINGS.temperature,
        });
      })
      .catch(() => {
        message.error('加载项目设置失败');
        form.setFieldsValue(DEFAULT_SETTINGS);
      })
      .finally(() => setLoading(false));
  }, [id, form]);

  // ── 保存故事核心设置（含 targetWords）─────────────────────
  const handleSave = async (values: StoryCoreSettings) => {
    if (!id) return;
    setSaving(true);
    try {
      await projectApi.update(id, { story_core: values } as any);
      message.success('设置已保存');
    } catch {
      message.error('保存失败');
    } finally {
      setSaving(false);
    }
  };

  // ── 保存书籍简介 ──────────────────────────────────────────
  const handleSaveDescription = async () => {
    if (!id) return;
    setDescSaving(true);
    try {
      await projectApi.update(id, { description });
      message.success('书籍简介已保存');
    } catch {
      message.error('保存失败');
    } finally {
      setDescSaving(false);
    }
  };

  const handleExportBackup = async () => {
    if (!id) return;
    try {
      const blob = await backupApi.download(id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'project-backup.json';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      message.success('备份导出成功');
    } catch {
      message.error('导出备份失败');
    }
  };

  const handleImportBackup = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!id || !file) return;
    if (!file.name.endsWith('.json')) {
      message.warning('请选择 .json 备份文件');
      e.target.value = '';
      return;
    }
    try {
      const { restored_count } = await backupApi.restore(id, file);
      message.success(`恢复完成，已写入 ${restored_count} 条记录，页面即将刷新`);
      setTimeout(() => window.location.reload(), 800);
    } catch {
      message.error('导入备份失败，请检查文件是否为该项目备份');
    } finally {
      e.target.value = '';
    }
  };

  const handleCheckConsistency = async () => {
    if (!id) return;
    setCheckLoading(true);
    setCheckResult(null);
    try {
      const res = await projectApi.consistencyCheck(id);
      setCheckResult(res.data);
      if (res.data.healthy) {
        message.success('设定一致性检查通过，未发现冲突');
      } else {
        message.warning(`发现 ${res.data.conflicts.length} 个设定冲突，请查看下方详情`);
      }
    } catch {
      message.error('检查失败');
    } finally {
      setCheckLoading(false);
    }
  };

  const severityTag = (severity: string) => {
    if (severity === 'critical') {
      return <Tag color="red">严重</Tag>;
    }
    return <Tag color="orange">警告</Tag>;
  };

  const typeLabel = (type: string) => {
    const map: Record<string, string> = {
      protagonist_name: '主角名字',
      entity_conflict: '实体设定',
      faction_name: '组织名称',
    };
    return map[type] || type;
  };

  return (
    <AppLayout projectId={id!}>
      <Title level={3} style={{ marginBottom: 24 }}>项目设置</Title>

      {/* ── 书籍简介 ────────────────────────────────────────── */}
      <Card
        style={{ maxWidth: 800, marginBottom: 16 }}
        title="📖 书籍简介"
        extra={
          <Button
            type="primary"
            onClick={handleSaveDescription}
            loading={descSaving}
          >
            保存简介
          </Button>
        }
      >
        <Spin spinning={loading}>
          <TextArea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={8}
            placeholder="输入书籍简介..."
            style={{ marginBottom: 8 }}
          />
          <Text type="secondary" style={{ fontSize: 12 }}>
            {description.length} 字
          </Text>
        </Spin>
      </Card>

      {/* ── 全书卷纲 ────────────────────────────────────────── */}
      {outline && (
        <Card
          style={{ maxWidth: 800, marginBottom: 16 }}
          title="📚 全书卷纲"
        >
          <Spin spinning={loading}>
            <Row gutter={16} style={{ marginBottom: 16 }}>
              <Col span={6}>
                <Statistic
                  title="总字数目标"
                  value={outline.total_target_words ?? '-'}
                  suffix="字"
                  valueStyle={{ fontSize: 18 }}
                />
              </Col>
              <Col span={6}>
                <Statistic
                  title="总卷数"
                  value={outline.total_volumes ?? '-'}
                  suffix="卷"
                  valueStyle={{ fontSize: 18 }}
                />
              </Col>
              <Col span={6}>
                <Statistic
                  title="总章数"
                  value={outline.total_chapters ?? '-'}
                  suffix="章"
                  valueStyle={{ fontSize: 18 }}
                />
              </Col>
              <Col span={6}>
                <Statistic
                  title="每章字数"
                  value={outline.words_per_chapter ?? '-'}
                  suffix="字"
                  valueStyle={{ fontSize: 18 }}
                />
              </Col>
            </Row>

            {outline.style_reference && (
              <Alert
                message={`对标风格：${outline.style_reference}`}
                type="info"
                showIcon
                style={{ marginBottom: 16 }}
              />
            )}

            {outline.volumes && outline.volumes.length > 0 && (
              <Collapse
                defaultActiveKey={outline.volumes.map((_, i) => String(i))}
                items={outline.volumes.map((vol, i) => ({
                  key: String(i),
                  label: (
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <Tag color="blue">第 {i + 1} 卷</Tag>
                      <Text strong>{vol.title}</Text>
                      {vol.chapters_range && (
                        <Tag>{vol.chapters_range} 章</Tag>
                      )}
                      {vol.chapter_count && (
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          {vol.chapter_count} 章
                        </Text>
                      )}
                    </div>
                  ),
                  children: (
                    <Descriptions column={1} size="small" bordered>
                      {vol.core_conflict && (
                        <Descriptions.Item label="核心冲突">
                          {vol.core_conflict}
                        </Descriptions.Item>
                      )}
                      {vol.description && (
                        <Descriptions.Item label="卷述">
                          <Paragraph style={{ marginBottom: 0, whiteSpace: 'pre-wrap' }}>
                            {vol.description}
                          </Paragraph>
                        </Descriptions.Item>
                      )}
                    </Descriptions>
                  ),
                }))}
              />
            )}
          </Spin>
        </Card>
      )}

      {/* ── 创作设置 ────────────────────────────────────────── */}
      <Card style={{ maxWidth: 800 }} title="⚙️ 创作参数">
        <Spin spinning={loading}>
          <Form
            form={form}
            layout="vertical"
            onFinish={handleSave}
            initialValues={DEFAULT_SETTINGS}
          >
            <Form.Item label="创作风格" name="style">
              <Select
                options={[
                  { value: 'default', label: '默认风格' },
                  { value: 'detailed', label: '详细描写型' },
                  { value: 'concise', label: '简洁利落型' },
                  { value: 'literary', label: '文学性强' },
                ]}
                placeholder="选择 AI 创作风格"
              />
            </Form.Item>
            <Form.Item
              label="每章目标字数"
              name="targetWords"
              extra={
                outline?.words_per_chapter
                  ? `卷纲设定：每章 ${outline.words_per_chapter} 字（生成时以此值为准）`
                  : '生成章节时的建议字数，影响 max_tokens 上限'
              }
            >
              <InputNumber min={100} style={{ width: '100%' }} placeholder="如 5000" />
            </Form.Item>
            <Form.Item label="模型温度 (0-2)" name="temperature">
              <InputNumber step={0.1} min={0} max={2} style={{ width: '100%' }} placeholder="0.8" />
            </Form.Item>
            <Form.Item>
              <Button type="primary" htmlType="submit" loading={saving}>
                保存设置
              </Button>
            </Form.Item>
          </Form>
        </Spin>
      </Card>

      {/* ── 设定一致性检查 ──────────────────────────────────────── */}
      <Card
        style={{ maxWidth: 800, marginTop: 16 }}
        title="设定一致性检查"
        extra={
          <Button
            type="primary"
            ghost
            icon={<span>🔍</span>}
            loading={checkLoading}
            onClick={handleCheckConsistency}
          >
            检查冲突
          </Button>
        }
      >
        {!checkResult ? (
          <Alert
            message="点击「检查冲突」对比故事核心、角色设定、世界观之间的关键信息，及时发现设定矛盾"
            type="info"
            showIcon
            style={{ marginTop: 4 }}
          />
        ) : checkResult.healthy ? (
          <Result
            status="success"
            title="通过"
            subTitle="未发现设定冲突"
          />
        ) : (
          <List
            size="small"
            dataSource={checkResult.conflicts}
            locale={{ emptyText: '未检测到冲突' }}
            renderItem={(c) => (
              <List.Item>
                <div style={{ width: '100%' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                    <Tag color="blue">{typeLabel(c.type)}</Tag>
                    {severityTag(c.severity)}
                  </div>
                  <div style={{ color: '#555' }}>{c.detail}</div>
                  <div style={{ fontSize: 11, color: '#999', marginTop: 2 }}>
                    涉及字段：{c.sources.join(' / ')}
                  </div>
                </div>
              </List.Item>
            )}
          />
        )}
      </Card>
      {/* ── 备份 ───────────────────────────────────────────────── */}
      <Card
        style={{ maxWidth: 800, marginTop: 16 }}
        title="备份与恢复"
        extra={
          <span style={{ fontSize: 12, color: '#999' }}>
            整项目数据：章节、角色、世界观、伏笔、知识等
          </span>
        }
      >
        <div style={{ display: 'flex', gap: 12, marginBottom: 12 }}>
          <Button type="primary" onClick={handleExportBackup}>
            导出备份
          </Button>
          <Button
            onClick={() => {
              const el = document.getElementById('backup-file-input');
              el?.click();
            }}
          >
            导入备份
          </Button>
        </div>
        <input
          id="backup-file-input"
          type="file"
          accept=".json,application/json"
          style={{ display: 'none' }}
          onChange={handleImportBackup}
        />
        <Alert
          message="导出会生成 .json 文件包含全部项目数据；导入会清空该项目现有数据再写入，请谨慎操作"
          type="warning"
          showIcon
          style={{ marginTop: 4 }}
        />
      </Card>
    </AppLayout>
  );
}
