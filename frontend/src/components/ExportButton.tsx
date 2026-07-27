import { useCallback, useState } from 'react';
import { Button, message, Popconfirm } from 'antd';
import { FileWordOutlined, ExportOutlined } from '@ant-design/icons';
import { exportApi } from '../services/api';

export interface ExportButtonProps {
  projectId: string;
  projectName: string;
  /** 单章模式：chapterId + title；为空则默认导出全本 */
  chapterId?: string;
  chapterTitle?: string;
  type?: 'default' | 'primary';
  size?: 'small' | 'middle' | 'large';
  label?: string;
  /** 单章模式下显示文案 */
  chapterLabel?: string;
}

export default function ExportButton({
  projectId,
  projectName,
  chapterId,
  chapterTitle,
  type = 'default',
  size = 'middle',
  label = '导出全本',
  chapterLabel = '导出本章',
}: ExportButtonProps) {
  const [downloading, setDownloading] = useState(false);

  const handleDownload = useCallback(async () => {
    if (!projectId) {
      message.warning('项目未就绪');
      return;
    }
    setDownloading(true);
    try {
      if (chapterId && chapterTitle) {
        await exportApi.downloadChapter(projectId, projectName, chapterId, chapterTitle);
        message.success(`已导出章节《${chapterTitle}》`);
      } else {
        await exportApi.downloadFull(projectId, projectName);
        message.success(`已导出全本《${projectName}》`);
      }
    } catch (e: any) {
      message.error(`导出失败：${e?.message || '未知错误'}`);
    } finally {
      setDownloading(false);
    }
  }, [projectId, projectName, chapterId, chapterTitle]);

  const content = chapterId && chapterTitle
    ? <>{chapterLabel}</>
    : <>{label}</>;

  const icon = chapterId && chapterTitle ? <FileWordOutlined /> : <ExportOutlined />;

  return (
    <Popconfirm
      title="确认导出"
      description={chapterId ? `导出单章《${chapterTitle}》为 .docx 文件` : `导出全本《${projectName}》为 .docx 文件（含全部章节正文）`}
      onConfirm={handleDownload}
      okText="导出"
      cancelText="取消"
    >
      <Button
        type={type}
        size={size}
        icon={icon}
        loading={downloading}
        disabled={!projectId}
      >
        {content}
      </Button>
    </Popconfirm>
  );
}
