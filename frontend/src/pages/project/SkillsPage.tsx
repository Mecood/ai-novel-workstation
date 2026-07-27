// @ts-nocheck
import { useParams } from 'react-router-dom';
import { useState, useEffect, useCallback } from 'react';
import { Card, Spin, message, Typography, Table, Switch, Tag, Empty, Space, Button } from 'antd';
import { ThunderboltOutlined, ReloadOutlined } from '@ant-design/icons';
import AppLayout from '../../components/layout/AppLayout';
import { skillsApi } from '../../services/api';

const { Title, Text } = Typography;

const CATEGORY_COLORS: Record<string, string> = {
  writing: '#1890ff',
  style: '#722ed1',
  review: '#52c41a',
  worldbuilding: '#fa8c16',
  publishing: '#eb2f96',
};

const CATEGORY_LABELS: Record<string, string> = {
  writing: '写作',
  style: '风格',
  review: '审查',
  worldbuilding: '世界观',
  publishing: '发布',
};

interface SkillDefinition {
  name: string;
  category: string;
  description: string;
  version: string;
  tasks: string[];
  triggers: string[];
  priority: number;
}

interface ProjectSkill {
  id: string;
  skill_name: string;
  skill_category: string;
  enabled: boolean;
}

export default function SkillsPage() {
  const { id } = useParams();
  const [builtinSkills, setBuiltinSkills] = useState<SkillDefinition[]>([]);
  const [projectSkills, setProjectSkills] = useState<ProjectSkill[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchSkills = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    try {
      const [builtinRes, projectRes] = await Promise.all([
        skillsApi.listBuiltin(),
        skillsApi.listProject(id),
      ]);
      setBuiltinSkills(builtinRes.data || []);
      setProjectSkills(projectRes.data?.project_skills || projectRes.data || []);
    } catch {
      message.error('加载 Skill 列表失败');
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => { fetchSkills(); }, [fetchSkills]);

  const isSkillEnabled = (skillName: string): boolean => {
    return projectSkills.some(s => s.skill_name === skillName && s.enabled);
  };

  const handleToggle = async (skill: SkillDefinition, checked: boolean) => {
    const prevSkills = [...projectSkills];
    try {
      if (checked) {
        await skillsApi.enable(id!, skill.name, skill.category);
      } else {
        await skillsApi.disable(id!, skill.name);
      }
      await fetchSkills();
    } catch {
      message.error(`${checked ? '启用' : '停用'}失败`);
      setProjectSkills(prevSkills);
    }
  };

  const builtinColumns = [
    {
      title: 'Skill 名称',
      dataIndex: 'name',
      key: 'name',
      width: 200,
      render: (name: string) => <Text strong>{name}</Text>,
    },
    {
      title: '分类',
      dataIndex: 'category',
      key: 'category',
      width: 100,
      render: (cat: string) => (
        <Tag color={CATEGORY_COLORS[cat] || '#8c8c8c'}>
          {CATEGORY_LABELS[cat] || cat}
        </Tag>
      ),
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
    },
    {
      title: '适用任务',
      dataIndex: 'tasks',
      key: 'tasks',
      width: 180,
      render: (tasks: string[]) => (
        <Space size={4} wrap>
          {(tasks || []).map((t) => (
            <Tag key={t} style={{ fontSize: 11 }}>{t}</Tag>
          ))}
        </Space>
      ),
    },
    {
      title: '启用',
      key: 'enabled',
      width: 80,
      align: 'center' as const,
      render: (_: unknown, record: SkillDefinition) => (
        <Switch
          size="small"
          checked={isSkillEnabled(record.name)}
          onChange={(checked) => handleToggle(record, checked)}
        />
      ),
    },
  ];

  return (
    <AppLayout>
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <Space style={{ width: '100%', justifyContent: 'space-between' }}>
          <Space>
            <ThunderboltOutlined style={{ fontSize: 20, color: '#722ed1' }} />
            <Title level={3} style={{ margin: 0 }}>Skill 体系</Title>
          </Space>
          <Space>
            <Text type="secondary">{builtinSkills.length} 个内置 Skill</Text>
            <ReloadOutlined onClick={fetchSkills} style={{ cursor: 'pointer' }} />
          </Space>
        </Space>

        <Text type="secondary">
          Skill 是项目可启用的 AI 能力模块。启用后，AI 调用会自动注入匹配的 Skill 提示词。
        </Text>

        <Card
          title={<Text strong>📦 内置 Skill ({builtinSkills.length})</Text>}
          loading={loading}
        >
          {builtinSkills.length === 0 ? (
            <Empty description="暂无内置 Skill。请检查 backend/app/skills/ 目录。" />
          ) : (
            <Table
              dataSource={builtinSkills}
              columns={builtinColumns}
              rowKey="name"
              size="middle"
              pagination={false}
              scroll={{ y: 400 }}
            />
          )}
        </Card>

        <Card
          title={<Text strong>📋 已启用的项目 Skill</Text>}
          loading={loading}
        >
          {projectSkills.filter((s) => s.enabled).length === 0 ? (
            <Empty description="该项目尚未启用任何 Skill。在上方表中打开开关即可启用。" />
          ) : (
            <Table
              dataSource={projectSkills.filter((s) => s.enabled)}
              columns={[
                { title: '名称', dataIndex: 'skill_name', key: 'name' },
                {
                  title: '分类',
                  dataIndex: 'skill_category',
                  key: 'cat',
                  render: (cat: string) => (
                    <Tag color={CATEGORY_COLORS[cat] || '#8c8c8c'}>
                      {CATEGORY_LABELS[cat] || cat}
                    </Tag>
                  ),
                },
                {
                  title: '操作',
                  key: 'action',
                  width: 80,
                  render: (_: unknown, record: ProjectSkill) => (
                    <Button
                      size="small"
                      danger
                      type="text"
                      onClick={() => handleToggle(
                        { name: record.skill_name, category: record.skill_category } as SkillDefinition,
                        false
                      )}
                    >
                      停用
                    </Button>
                  ),
                },
              ]}
              rowKey="skill_name"
              size="middle"
              pagination={false}
            />
          )}
        </Card>
      </Space>
    </AppLayout>
  );
}
