import { useEditor, EditorContent, useEditorState } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import Underline from '@tiptap/extension-underline';
import { Button, Divider } from 'antd';
import {
  BoldOutlined,
  ItalicOutlined,
  UnderlineOutlined,
  StrikethroughOutlined,
  OrderedListOutlined,
  UnorderedListOutlined,
  UndoOutlined,
  RedoOutlined,
} from '@ant-design/icons';

interface ContentMark {
  id: string;
  type: 'reference';
  line_start: number;
  line_end: number;
  text: string;
  created_at: string;
}

interface TiptapEditorProps {
  value: string;
  onChange: (text: string) => void;
  editable?: boolean;
  height?: number;
  content_marks?: ContentMark[];
}

const TiptapEditor: React.FC<TiptapEditorProps> = ({
  value,
  onChange,
  editable = true,
  height = 500,
  content_marks = [],
}) => {
  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        heading: { levels: [1, 2, 3] },
      }),
      Underline,
    ],
    content: value,
    editable,
    onUpdate: ({ editor: ed }) => {
      onChange(ed.getText());
    },
  });

  // 同步外部 value
  if (editor && value !== editor.getText()) {
    queueMicrotask(() => {
      if (editor && value !== editor.getText()) {
        editor.commands.setContent(value);
      }
    });
  }

  // 计算文档中段落数量（即行数）
  const paragraphs = useEditorState({
    editor,
    selector: (ctx) => {
      if (!ctx.editor) return 0;
      try {
        const anyDoc: any = ctx.editor.state.doc;
        const nodes = anyDoc.querySelectorAll ? anyDoc.querySelectorAll('paragraph') : undefined;
        return nodes ? nodes.length : 0;
      } catch {
        return Math.max(1, (value || '').split('\n').length);
      }
    },
  });
  const lineCount = paragraphs || Math.max(1, (value.split('\n').length));

  // 解析 content_marks 建立 lineNumber -> mark 映射
  const markMap: Record<number, ContentMark[]> = {};
  for (const m of content_marks) {
    const end = m.line_end ?? m.line_start;
    for (let ln = m.line_start; ln <= end; ln++) {
      if (!markMap[ln]) markMap[ln] = [];
      markMap[ln].push(m);
    }
  }

  if (!editor) return null;

  return (
    <div
      style={{
        border: '1px solid #d9d9d9',
        borderRadius: '6px',
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {/* Toolbar */}
      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: 4,
          padding: '6px 8px',
          borderBottom: '1px solid #d9d9d9',
          background: '#fafafa',
        }}
      >
        <Button size="small" type={editor.isActive('bold') ? 'primary' : 'text'}
          onClick={() => editor.chain().focus().toggleBold().run()} icon={<BoldOutlined />} />
        <Button size="small" type={editor.isActive('italic') ? 'primary' : 'text'}
          onClick={() => editor.chain().focus().toggleItalic().run()} icon={<ItalicOutlined />} />
        <Button size="small" type={editor.isActive('underline') ? 'primary' : 'text'}
          onClick={() => editor.chain().focus().toggleUnderline().run()} icon={<UnderlineOutlined />} />
        <Button size="small" type={editor.isActive('strike') ? 'primary' : 'text'}
          onClick={() => editor.chain().focus().toggleStrike().run()} icon={<StrikethroughOutlined />} />
        <Divider type="vertical" style={{ borderColor: '#d9d9d9' }} />
        <Button size="small" type={editor.isActive('heading', { level: 1 }) ? 'primary' : 'text'}
          onClick={() => editor.chain().focus().toggleHeading({ level: 1 }).run()}
          style={{ fontWeight: 700, fontSize: 14 }}>H1</Button>
        <Button size="small" type={editor.isActive('heading', { level: 2 }) ? 'primary' : 'text'}
          onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}
          style={{ fontWeight: 600 }}>H2</Button>
        <Button size="small" type={editor.isActive('heading', { level: 3 }) ? 'primary' : 'text'}
          onClick={() => editor.chain().focus().toggleHeading({ level: 3 }).run()}
          style={{ fontWeight: 500 }}>H3</Button>
        <Divider type="vertical" style={{ borderColor: '#d9d9d9' }} />
        <Button size="small" type={editor.isActive('bulletList') ? 'primary' : 'text'}
          onClick={() => editor.chain().focus().toggleBulletList().run()} icon={<UnorderedListOutlined />} />
        <Button size="small" type={editor.isActive('orderedList') ? 'primary' : 'text'}
          onClick={() => editor.chain().focus().toggleOrderedList().run()} icon={<OrderedListOutlined />} />
        <Divider type="vertical" style={{ borderColor: '#d9d9d9' }} />
        <Button size="small" type="text"
          onClick={() => editor.chain().focus().undo().run()}
          disabled={!editor.can().undo()} icon={<UndoOutlined />} />
        <Button size="small" type="text"
          onClick={() => editor.chain().focus().redo().run()}
          disabled={!editor.can().redo()} icon={<RedoOutlined />} />
      </div>

      {/* Editor area with line numbers */}
      <div style={{ display: 'flex', flex: 1, minHeight: `${height}px` }}>
        {/* Line number gutter */}
        <div
          style={{
            width: 36,
            background: '#f5f5f5',
            borderRight: '1px solid #e8e8e8',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            paddingTop: 12,
            userSelect: 'none',
            flexShrink: 0,
            overflow: 'hidden',
          }}
        >
          {Array.from({ length: lineCount }, (_, i) => {
            const ln = i + 1;
            const marks = markMap[ln];
            return (
              <div
                key={ln}
                style={{
                  height: 24,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  width: '100%',
                  fontSize: 11,
                  color: marks ? '#faad14' : '#8c8c8c',
                  fontWeight: marks ? 600 : 400,
                }}
                title={marks ? marks.map(m => m.text).join('、') : undefined}
              >
                {marks ? '📌' : ln}
              </div>
            );
          })}
        </div>

        {/* Editor pane */}
        <EditorContent
          editor={editor}
          style={{
            flex: 1,
            minHeight: `${height}px`,
            height: 'auto',
            overflowY: 'auto',
            padding: '12px 16px',
            outline: 'none',
            fontSize: 14,
            lineHeight: '24px',
          }}
        />
      </div>
    </div>
  );
};

export default TiptapEditor;
