/**
 * ============================================================
 * MubloEditor.js
 * (c) 2025 Mublo
 * Author: Mublo
 * Licensed under the MIT License
 * https://opensource.org/licenses/MIT
 * ============================================================
 *
 * MubloEditor는 Mublo Framework 전용 경량 WYSIWYG 에디터이다.
 * TinyMCE, CKEditor 등 외부 의존성 없이 순수 JavaScript로 구현되었다.
 *
 * ------------------------------------------------------------
 * 핵심 설계 철학
 * ------------------------------------------------------------
 *
 * 1. 선언적 사용 (Declarative)
 *    - data-* 속성으로 에디터 옵션 지정
 *    - JS 코드 없이 HTML만으로 에디터 생성 가능
 *
 * 2. MubloRequest 통합
 *    - syncAllEditors() 자동 지원
 *    - 폼 제출 시 자동 동기화
 *
 * 3. 확장 가능한 플러그인 시스템
 *    - 커스텀 툴바 버튼 추가 가능
 *    - 이미지 업로드 핸들러 교체 가능
 *    - 이벤트 훅 제공
 *
 * 4. 다크 모드 & Bootstrap 5 호환
 *    - CSS 변수 기반 테마
 *    - Bootstrap 클래스 활용
 *
 * ------------------------------------------------------------
 * 플러그인 시스템
 * ------------------------------------------------------------
 *
 * [이미지 업로드 플러그인 예시]
 *
 * MubloEditor.registerPlugin('myImageUploader', (editor) => {
 *     editor.setImageUploadHandler(async (blobInfo, progress) => {
 *         // blobInfo.blob()     - File/Blob 객체
 *         // blobInfo.filename() - 파일명
 *         // blobInfo.base64()   - Base64 문자열
 *         // progress(percent)   - 진행률 콜백 (0-100)
 *
 *         const formData = new FormData();
 *         formData.append('file', blobInfo.blob(), blobInfo.filename());
 *
 *         const res = await fetch('/api/upload', {
 *             method: 'POST',
 *             body: formData
 *         });
 *
 *         if (!res.ok) throw new Error('Upload failed');
 *
 *         const data = await res.json();
 *         return data.url;  // 이미지 URL 반환
 *     });
 * });
 *
 * ------------------------------------------------------------
 * API
 * ------------------------------------------------------------
 *
 * MubloEditor.create(selector, options)  - 에디터 생성
 * MubloEditor.get(id)                    - ID로 에디터 인스턴스 가져오기
 * MubloEditor.getAll()                   - 모든 에디터 인스턴스
 * MubloEditor.destroy(id)                - 에디터 제거
 * MubloEditor.registerPlugin(name, fn)   - 플러그인 등록
 *
 * [인스턴스 메서드]
 * editor.getHTML()                      - HTML 콘텐츠 반환
 * editor.setHTML(html)                  - HTML 콘텐츠 설정
 * editor.getText()                      - 텍스트만 반환
 * editor.isEmpty()                      - 비어있는지 확인
 * editor.focus()                        - 에디터에 포커스
 * editor.blur()                         - 포커스 해제
 * editor.destroy()                      - 에디터 제거
 * editor.sync()                         - textarea와 동기화
 * editor.insertContent(html)            - HTML 삽입
 * editor.insertImage(url, alt)          - 이미지 삽입
 * editor.setImageUploadHandler(fn)      - 이미지 업로드 핸들러 설정
 * editor.on(event, callback)            - 이벤트 리스너 등록
 * editor.off(event, callback)           - 이벤트 리스너 제거
 * editor.fire(event, data)              - 이벤트 발생
 *
 * ============================================================
 */

const MubloEditor = (() => {
    'use strict';

    const VERSION = '1.2.0';
    const EDITOR_CLASS = 'mublo-editor';
    const EDITOR_WRAPPER_CLASS = 'mublo-editor-wrapper';
    const EDITOR_TOOLBAR_CLASS = 'mublo-editor-toolbar';
    const EDITOR_CONTENT_CLASS = 'mublo-editor-content';

    const TOOLBAR_ITEMS = {
        bold: {
            icon: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M6 4h8a4 4 0 0 1 4 4 4 4 0 0 1-4 4H6z"/><path d="M6 12h9a4 4 0 0 1 4 4 4 4 0 0 1-4 4H6z"/></svg>',
            title: '굵게 (Ctrl+B)',
            command: 'bold'
        },
        italic: {
            icon: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="19" y1="4" x2="10" y2="4"/><line x1="14" y1="20" x2="5" y2="20"/><line x1="15" y1="4" x2="9" y2="20"/></svg>',
            title: '기울임 (Ctrl+I)',
            command: 'italic'
        },
        underline: {
            icon: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 3v7a6 6 0 0 0 6 6 6 6 0 0 0 6-6V3"/><line x1="4" y1="21" x2="20" y2="21"/></svg>',
            title: '밑줄 (Ctrl+U)',
            command: 'underline'
        },
        strikethrough: {
            icon: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17.3 4.9c-2.3-.6-4.4-1-6.2-.9-2.7 0-5.3.7-5.3 3.6 0 1.5 1.8 3.3 3.6 3.9h.2m8.2 3.7c.3.4.4.8.4 1.3 0 2.9-2.7 3.6-6.2 3.6-2.3 0-4.4-.3-6.2-.9M4 11.5h16"/></svg>',
            title: '취소선',
            command: 'strikeThrough'
        },
        separator: { type: 'separator' },
        heading: {
            icon: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 4v16"/><path d="M18 4v16"/><path d="M6 12h12"/></svg>',
            title: '제목',
            type: 'dropdown',
            items: [
                { label: '제목 1', command: 'formatBlock', value: 'h1' },
                { label: '제목 2', command: 'formatBlock', value: 'h2' },
                { label: '제목 3', command: 'formatBlock', value: 'h3' },
                { label: '본문', command: 'formatBlock', value: 'p' }
            ]
        },
        fontname: {
            icon: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 7V4h16v3"/><path d="M9 20h6"/><line x1="12" y1="4" x2="12" y2="20"/></svg>',
            title: '글꼴',
            type: 'dropdown',
            items: [
                { label: '기본 서체', command: 'fontName', value: 'inherit' },
                { label: 'Arial', command: 'fontName', value: 'Arial' },
                { label: 'Verdana', command: 'fontName', value: 'Verdana' },
                { label: 'Times New Roman', command: 'fontName', value: 'Times New Roman' },
                { label: 'Courier New', command: 'fontName', value: 'Courier New' },
                { label: '맑은 고딕', command: 'fontName', value: 'Malgun Gothic' },
                { label: '굴림', command: 'fontName', value: 'Gulim' },
                { label: '바탕', command: 'fontName', value: 'Batang' }
            ]
        },
        fontsize: {
            icon: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="4 7 4 4 20 4 20 7"/><line x1="9" y1="20" x2="15" y2="20"/><line x1="12" y1="4" x2="12" y2="20"/></svg>',
            title: '글자 크기',
            type: 'dropdown',
            items: [
                { label: '작게', command: 'fontSize', value: '2' },
                { label: '보통', command: 'fontSize', value: '3' },
                { label: '크게', command: 'fontSize', value: '4' },
                { label: '아주 크게', command: 'fontSize', value: '5' }
            ]
        },
        subscript: {
            icon: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 5l11 11"/><path d="M16 5l-11 11"/><path d="M20 20h2v2h-2z"/></svg>',
            title: '아래 첨자',
            command: 'subscript'
        },
        superscript: {
            icon: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 19l11-11"/><path d="M16 19l-11-11"/><path d="M20 4h2v2h-2z"/></svg>',
            title: '위 첨자',
            command: 'superscript'
        },
        forecolor: {
            icon: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 20h16"/><path d="M6.5 16L9.354 5h5.292L18 16" fill="currentColor" opacity="0.2"/></svg>',
            title: '글자 색상',
            type: 'color',
            command: 'foreColor'
        },
        backcolor: {
            icon: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2" fill="currentColor" opacity="0.2"/></svg>',
            title: '배경 색상',
            type: 'color',
            command: 'hiliteColor'
        },
        alignleft: {
            icon: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="15" y2="12"/><line x1="3" y1="18" x2="18" y2="18"/></svg>',
            title: '왼쪽 정렬',
            command: 'justifyLeft'
        },
        aligncenter: {
            icon: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="3" y1="6" x2="21" y2="6"/><line x1="6" y1="12" x2="18" y2="12"/><line x1="4" y1="18" x2="20" y2="18"/></svg>',
            title: '가운데 정렬',
            command: 'justifyCenter'
        },
        alignright: {
            icon: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="3" y1="6" x2="21" y2="6"/><line x1="9" y1="12" x2="21" y2="12"/><line x1="6" y1="18" x2="21" y2="18"/></svg>',
            title: '오른쪽 정렬',
            command: 'justifyRight'
        },
        orderedlist: {
            icon: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="10" y1="6" x2="21" y2="6"/><line x1="10" y1="12" x2="21" y2="12"/><line x1="10" y1="18" x2="21" y2="18"/><path d="M4 6h2v2H4z" fill="currentColor"/><path d="M4 12h2v2H4z" fill="currentColor"/><path d="M4 18h2v2H4z" fill="currentColor"/></svg>',
            title: '번호 목록',
            command: 'insertOrderedList'
        },
        unorderedlist: {
            icon: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="9" y1="6" x2="21" y2="6"/><line x1="9" y1="12" x2="21" y2="12"/><line x1="9" y1="18" x2="21" y2="18"/><circle cx="4" cy="6" r="1.5" fill="currentColor"/><circle cx="4" cy="12" r="1.5" fill="currentColor"/><circle cx="4" cy="18" r="1.5" fill="currentColor"/></svg>',
            title: '글머리 목록',
            command: 'insertUnorderedList'
        },
        indent: {
            icon: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="3" y1="6" x2="21" y2="6"/><line x1="9" y1="12" x2="21" y2="12"/><line x1="9" y1="18" x2="21" y2="18"/><polyline points="3 9 6 12 3 15"/></svg>',
            title: '들여쓰기',
            command: 'indent'
        },
        outdent: {
            icon: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="3" y1="6" x2="21" y2="6"/><line x1="9" y1="12" x2="21" y2="12"/><line x1="9" y1="18" x2="21" y2="18"/><polyline points="6 9 3 12 6 15"/></svg>',
            title: '내어쓰기',
            command: 'outdent'
        },
        link: {
            icon: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>',
            title: '링크 (Ctrl+K)',
            type: 'link'
        },
        unlink: {
            icon: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18.84 12.25l1.72-1.71a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M5.17 11.75L3.45 13.46a5 5 0 0 0 7.07 7.07l1.71-1.71"/><line x1="2" y1="2" x2="22" y2="22"/></svg>',
            title: '링크 제거',
            command: 'unlink'
        },
        image: {
            icon: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>',
            title: '이미지',
            type: 'image'
        },
        table: {
            icon: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><line x1="3" y1="9" x2="21" y2="9"/><line x1="3" y1="15" x2="21" y2="15"/><line x1="9" y1="3" x2="9" y2="21"/><line x1="15" y1="3" x2="15" y2="21"/></svg>',
            title: '테이블',
            type: 'table'
        },
        hr: {
            icon: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="3" y1="12" x2="21" y2="12"/></svg>',
            title: '수평선',
            command: 'insertHorizontalRule'
        },
        video: {
            icon: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="4" width="20" height="16" rx="2"/><polygon points="10 8 16 12 10 16 10 8" fill="currentColor"/></svg>',
            title: '동영상',
            type: 'video'
        },
        blockquote: {
            icon: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 21c3 0 7-1 7-8V5c0-1.25-.756-2.017-2-2H4c-1.25 0-2 .75-2 1.972V11c0 1.25.75 2 2 2 1 0 1 0 1 1v1c0 1-1 2-2 2s-1 .008-1 1.031V21c0 1 0 1 1 1z"/><path d="M15 21c3 0 7-1 7-8V5c0-1.25-.757-2.017-2-2h-4c-1.25 0-2 .75-2 1.972V11c0 1.25.75 2 2 2h.75c0 2.25.25 4-2.75 4v3c0 1 0 1 1 1z"/></svg>',
            title: '인용구',
            command: 'formatBlock',
            value: 'blockquote'
        },
        code: {
            icon: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/></svg>',
            title: '코드 블록',
            command: 'formatBlock',
            value: 'pre'
        },
        removeformat: {
            icon: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 7V4h16v3"/><path d="M9 20h6"/><line x1="4" y1="20" x2="20" y2="4"/></svg>',
            title: '서식 제거',
            command: 'removeFormat'
        },
        selectall: {
            icon: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 9h6v6H9z"/></svg>',
            title: '전체 선택 (Ctrl+A)',
            command: 'selectAll'
        },
        print: {
            icon: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 6 2 18 2 18 9"/><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><rect x="6" y="14" width="12" height="8"/></svg>',
            title: '인쇄',
            type: 'print'
        },
        undo: {
            icon: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"/></svg>',
            title: '실행 취소 (Ctrl+Z)',
            command: 'undo'
        },
        redo: {
            icon: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>',
            title: '다시 실행 (Ctrl+Y)',
            command: 'redo'
        },
        fullscreen: {
            icon: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="15 3 21 3 21 9"/><polyline points="9 21 3 21 3 15"/><line x1="21" y1="3" x2="14" y2="10"/><line x1="3" y1="21" x2="10" y2="14"/></svg>',
            iconExit: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="4 14 10 14 10 20"/><polyline points="20 10 14 10 14 4"/><line x1="14" y1="10" x2="21" y2="3"/><line x1="3" y1="21" x2="10" y2="14"/></svg>',
            title: '전체화면',
            type: 'fullscreen'
        },
        source: {
            icon: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>',
            title: 'HTML 소스',
            type: 'source'
        },
        findreplace: {
            icon: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>',
            title: '찾기/바꾸기 (Ctrl+F)',
            type: 'findreplace'
        }
    };

    const TOOLBAR_PRESETS = {
        minimal: ['bold', 'italic', 'separator', 'link'],
        basic: ['bold', 'italic', 'underline', 'separator', 'alignleft', 'aligncenter', 'alignright', 'separator', 'orderedlist', 'unorderedlist', 'separator', 'link'],
        full: ['source', 'separator', 'undo', 'redo', 'separator', 'heading', 'fontname', 'fontsize', 'separator', 'bold', 'italic', 'underline', 'strikethrough', 'subscript', 'superscript', 'separator', 'forecolor', 'backcolor', 'separator', 'alignleft', 'aligncenter', 'alignright', 'separator', 'orderedlist', 'unorderedlist', 'indent', 'outdent', 'separator', 'link', 'unlink', 'image', 'video', 'table', 'separator', 'blockquote', 'code', 'hr', 'separator', 'removeformat', 'selectall', 'print', 'separator', 'findreplace', 'fullscreen']
    };

    const DEFAULT_COLORS = [
        '#000000', '#434343', '#666666', '#999999', '#b7b7b7', '#cccccc', '#d9d9d9', '#efefef', '#f3f3f3', '#ffffff',
        '#980000', '#ff0000', '#ff9900', '#ffff00', '#00ff00', '#00ffff', '#4a86e8', '#0000ff', '#9900ff', '#ff00ff',
        '#e6b8af', '#f4cccc', '#fce5cd', '#fff2cc', '#d9ead3', '#d0e0e3', '#c9daf8', '#cfe2f3', '#d9d2e9', '#ead1dc'
    ];

    const instances = new Map();
    const plugins = new Map();

    // =========================================================
    // BlobInfo 클래스 (TinyMCE 호환)
    // =========================================================
    class BlobInfo {
        constructor(file, base64 = null) {
            this._file = file;
            this._base64 = base64;
            this._id = 'blobid' + Date.now() + Math.random().toString(36).substr(2, 9);
        }

        id() { return this._id; }
        name() { return this._file.name; }
        filename() { return this._file.name; }
        blob() { return this._file; }
        base64() { return this._base64; }
        blobUri() { return URL.createObjectURL(this._file); }
        uri() { return this.blobUri(); }
    }

    // =========================================================
    // 유틸리티 함수
    // =========================================================
    function generateId() {
        return 'mublo-editor-' + Math.random().toString(36).substr(2, 9);
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function normalizeCodeText(html) {
        const temp = document.createElement('div');
        temp.innerHTML = html;
        let text = temp.innerText || temp.textContent || '';
        text = text.replace(/\r\n?/g, '\n').replace(/\u00a0/g, ' ');
        text = text.replace(/^\n/, '').replace(/\n$/, '');
        return text;
    }

    function convertCodeShortcodesToHtml(html) {
        if (!html || html.indexOf('[code]') === -1) return html;

        return html.replace(/\[code\]([\s\S]*?)\[\/code\]/gi, (_, codeContent) => {
            const codeText = normalizeCodeText(codeContent);
            return `<pre><code>${escapeHtml(codeText)}</code></pre>`;
        });
    }

    function sanitizeHtml(html) {
        if (!html) return '';

        // DOMParser를 이용한 자체 XSS 방어 로직
        // 외부 라이브러리 의존성 없이 브라우저 내장 파서를 사용하여 스크립트 실행을 방지합니다.
        try {
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, 'text/html');

            // 1. 블랙리스트 태그 제거
            const forbiddenTags = ['script', 'meta', 'applet', 'object', 'embed', 'base', 'form', 'link', 'style'];
            
            forbiddenTags.forEach(tag => {
                const elements = doc.querySelectorAll(tag);
                elements.forEach(el => el.remove());
            });

            // 2. 모든 요소의 속성 전수 검사
            const allElements = doc.body.querySelectorAll('*');
            allElements.forEach(el => {
                const attributes = Array.from(el.attributes);
                
                attributes.forEach(attr => {
                    const name = attr.name.toLowerCase();
                    // 제어 문자 및 공백 제거 후 검사 (우회 공격 방지)
                    const value = attr.value.toLowerCase().replace(/[\s\x00-\x1f]+/g, '');

                    // 2-1. 이벤트 핸들러 제거 (onmouseover, onclick 등)
                    if (name.startsWith('on')) {
                        el.removeAttribute(attr.name);
                    }

                    // 2-2. 위험한 프로토콜 제거 (javascript:, vbscript:)
                    if (value.includes('javascript:') || value.includes('vbscript:')) {
                        el.removeAttribute(attr.name);
                    }
                    
                    // 2-3. data: 프로토콜은 이미지 외에는 차단
                    if (value.startsWith('data:') && !value.startsWith('data:image/')) {
                        el.removeAttribute(attr.name);
                    }
                });
            });

            return doc.body.innerHTML;
        } catch (e) {
            console.error('[MubloEditor] Sanitization failed:', e);
            // 파싱 실패 시 텍스트만 반환하여 안전 확보
            const temp = document.createElement('div');
            temp.textContent = html;
            return temp.innerHTML;
        }
    }

    function fileToBase64(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(reader.result.split(',')[1]);
            reader.onerror = reject;
            reader.readAsDataURL(file);
        });
    }

    // =========================================================
    // Editor 클래스
    // =========================================================
    class Editor {
        constructor(element, options = {}) {
            this.originalElement = element;
            this.id = element.id || generateId();
            this.options = this._mergeOptions(options);
            this.isFullscreen = false;
            this.isSourceMode = false;
            this.savedRange = null;
            
            // 이벤트 시스템
            this._eventListeners = new Map();
            
            // 이미지 업로드 핸들러 (플러그인에서 교체 가능)
            this._imageUploadHandler = null;

            // 자동 저장 타이머
            this._autosaveTimer = null;

            // 이미지 리사이저
            this._selectedImage = null;
            this._resizer = null;

            // 전역 이벤트 핸들러 참조 (제거용)
            this._handlers = {};

            this._build();
            this._bindEvents();
            this._initPlugins();
            this.setHTML(element.value || '');
            instances.set(this.id, this);
            
            // ready 이벤트 발생
            this.fire('ready', { editor: this });
        }

        _mergeOptions(options) {
            const dataOptions = {};
            const el = this.originalElement;
            if (el.dataset.toolbar) dataOptions.toolbar = el.dataset.toolbar;
            if (el.dataset.height) dataOptions.height = parseInt(el.dataset.height, 10);
            if (el.dataset.placeholder) dataOptions.placeholder = el.dataset.placeholder;
            if (el.dataset.uploadUrl) dataOptions.uploadUrl = el.dataset.uploadUrl;
            if (el.dataset.toolbarItems) dataOptions.toolbarItems = el.dataset.toolbarItems.split(',').map(s => s.trim());
            if (el.dataset.showWordCount !== undefined) dataOptions.showWordCount = el.dataset.showWordCount === 'true';
            if (el.dataset.maxLength) dataOptions.maxLength = parseInt(el.dataset.maxLength, 10);
            if (el.dataset.autosave !== undefined) dataOptions.autosave = el.dataset.autosave === 'true';
            if (el.dataset.autosaveInterval) dataOptions.autosaveInterval = parseInt(el.dataset.autosaveInterval, 10);
            if (el.dataset.autosaveKey) dataOptions.autosaveKey = el.dataset.autosaveKey;

            return {
                toolbar: 'full',
                height: 300,
                minHeight: 150,
                placeholder: '',
                autofocus: false,
                readonly: false,
                colors: DEFAULT_COLORS,
                uploadUrl: null,
                maxFileSize: 5 * 1024 * 1024,
                allowedImageTypes: ['image/jpeg', 'image/png', 'image/gif', 'image/webp'],
                sanitize: true,
                automatic_uploads: true,
                images_upload_credentials: false,
                // 콜백 (하위 호환성)
                onChange: null,
                onFocus: null,
                onBlur: null,
                onImageUpload: null,
                onReady: null,
                // 스타일 핸들러
                images_upload_handler: null,
                // 글자 수 카운터
                showWordCount: false,
                maxLength: 0,  // 0 = 제한 없음
                // 자동 저장
                autosave: false,
                autosaveInterval: 30000,  // 30초
                autosaveKey: null,  // localStorage 키 (null이면 에디터 ID 사용)
                autosaveRestore: true,  // 페이지 로드 시 자동 복원
                ...dataOptions,
                ...options
            };
        }

        // =========================================================
        // 이벤트 시스템
        // =========================================================
        on(event, callback) {
            if (!this._eventListeners.has(event)) {
                this._eventListeners.set(event, []);
            }
            this._eventListeners.get(event).push(callback);
            return this;
        }

        off(event, callback) {
            if (!this._eventListeners.has(event)) return this;
            if (!callback) {
                this._eventListeners.delete(event);
            } else {
                const listeners = this._eventListeners.get(event);
                const index = listeners.indexOf(callback);
                if (index > -1) listeners.splice(index, 1);
            }
            return this;
        }

        fire(event, data = {}) {
            const listeners = this._eventListeners.get(event) || [];
            listeners.forEach(callback => {
                try {
                    callback({ ...data, type: event, target: this });
                } catch (e) {
                    console.error(`[MubloEditor] Event "${event}" handler error:`, e);
                }
            });
            return this;
        }

        // =========================================================
        // 이미지 업로드 핸들러 설정 (플러그인용)
        // =========================================================
        setImageUploadHandler(handler) {
            if (typeof handler !== 'function') {
                console.error('[MubloEditor] Image upload handler must be a function');
                return this;
            }
            this._imageUploadHandler = handler;
            return this;
        }

        getImageUploadHandler() {
            return this._imageUploadHandler;
        }

        // =========================================================
        // 빌드
        // =========================================================
        _build() {
            this.wrapper = document.createElement('div');
            this.wrapper.className = EDITOR_WRAPPER_CLASS;
            this.wrapper.id = this.id + '-wrapper';

            this.toolbar = this._buildToolbar();
            this.wrapper.appendChild(this.toolbar);

            this.contentArea = document.createElement('div');
            this.contentArea.className = EDITOR_CONTENT_CLASS;
            this.contentArea.contentEditable = !this.options.readonly;
            this.contentArea.style.minHeight = this.options.minHeight + 'px';
            this.contentArea.style.height = this.options.height + 'px';
            if (this.options.placeholder) {
                this.contentArea.dataset.placeholder = this.options.placeholder;
            }
            this.wrapper.appendChild(this.contentArea);

            this.sourceArea = document.createElement('textarea');
            this.sourceArea.className = 'mublo-editor-source';
            this.sourceArea.style.display = 'none';
            this.sourceArea.style.height = this.options.height + 'px';
            this.wrapper.appendChild(this.sourceArea);

            // 업로드 진행률 표시 영역
            this.progressBar = document.createElement('div');
            this.progressBar.className = 'mublo-editor-progress';
            this.progressBar.style.display = 'none';
            this.progressBar.innerHTML = '<div class="mublo-editor-progress-bar"></div>';
            this.wrapper.appendChild(this.progressBar);

            // 이미지 리사이저 요소 생성
            this._resizer = document.createElement('div');
            this._resizer.className = 'Mublo-resizer';
            this._resizer.innerHTML = '<div class="Mublo-resizer-handle Mublo-resizer-nw"></div><div class="Mublo-resizer-handle Mublo-resizer-ne"></div><div class="Mublo-resizer-handle Mublo-resizer-sw"></div><div class="Mublo-resizer-handle Mublo-resizer-se"></div>';
            this.wrapper.appendChild(this._resizer);

            // 글자 수 카운터
            if (this.options.showWordCount) {
                this.statusBar = document.createElement('div');
                this.statusBar.className = 'mublo-editor-statusbar';
                this.statusBar.innerHTML = '<span class="mublo-editor-wordcount"></span>';
                this.wrapper.appendChild(this.statusBar);
            }

            this.originalElement.style.display = 'none';
            this.originalElement.parentNode.insertBefore(this.wrapper, this.originalElement.nextSibling);

            // 엔터 키 입력 시 <div> 대신 <p> 태그가 생성되도록 설정
            this._ensureParagraphSeparator();
        }

        _buildToolbar() {
            const toolbar = document.createElement('div');
            toolbar.className = EDITOR_TOOLBAR_CLASS;
            const items = this.options.toolbarItems || TOOLBAR_PRESETS[this.options.toolbar] || TOOLBAR_PRESETS.full;

            items.forEach(name => {
                if (name === 'separator') {
                    const sep = document.createElement('span');
                    sep.className = 'mublo-editor-separator';
                    toolbar.appendChild(sep);
                    return;
                }
                const def = TOOLBAR_ITEMS[name];
                if (!def) return;
                const btn = this._createButton(name, def);
                if (btn) toolbar.appendChild(btn);
            });
            return toolbar;
        }

        _ensureParagraphSeparator() {
            try {
                document.execCommand('defaultParagraphSeparator', false, 'p');
            } catch (e) {
                // 브라우저 호환성 예외 처리
            }
        }

        _createButton(name, def) {
            if (def.type === 'dropdown') return this._createDropdown(name, def);
            if (def.type === 'color') return this._createColorPicker(name, def);

            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'mublo-editor-btn';
            btn.title = def.title;
            btn.innerHTML = def.icon;
            btn.dataset.cmd = name;
            btn.addEventListener('click', e => {
                e.preventDefault();
                this._handleCommand(name, def);
            });
            return btn;
        }

        _createDropdown(name, def) {
            const wrap = document.createElement('div');
            wrap.className = 'mublo-editor-dropdown';

            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'mublo-editor-btn mublo-editor-dropdown-btn';
            btn.title = def.title;
            btn.innerHTML = def.icon + '<svg class="mublo-editor-caret" width="10" height="10" viewBox="0 0 24 24"><polyline points="6 9 12 15 18 9" fill="none" stroke="currentColor" stroke-width="2"/></svg>';

            const menu = document.createElement('div');
            menu.className = 'mublo-editor-dropdown-menu';
            def.items.forEach(item => {
                const mi = document.createElement('button');
                mi.type = 'button';
                mi.className = 'mublo-editor-dropdown-item';
                mi.textContent = item.label;
                mi.addEventListener('click', e => {
                    e.preventDefault();
                    this._exec(item.command, item.value);
                    menu.classList.remove('show');
                });
                menu.appendChild(mi);
            });

            btn.addEventListener('click', e => {
                e.preventDefault();
                e.stopPropagation();
                this._closeAllDropdowns();
                menu.classList.toggle('show');
            });

            wrap.appendChild(btn);
            wrap.appendChild(menu);
            return wrap;
        }

        _createColorPicker(name, def) {
            const wrap = document.createElement('div');
            wrap.className = 'mublo-editor-dropdown mublo-editor-colorpicker';

            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'mublo-editor-btn';
            btn.title = def.title;
            btn.innerHTML = def.icon;

            const menu = document.createElement('div');
            menu.className = 'mublo-editor-dropdown-menu mublo-editor-color-menu';

            const palette = document.createElement('div');
            palette.className = 'mublo-editor-color-palette';
            this.options.colors.forEach(color => {
                const c = document.createElement('button');
                c.type = 'button';
                c.className = 'mublo-editor-color-btn';
                c.style.backgroundColor = color;
                c.title = color;
                c.addEventListener('click', e => {
                    e.preventDefault();
                    this._exec(def.command, color);
                    menu.classList.remove('show');
                });
                palette.appendChild(c);
            });
            menu.appendChild(palette);

            btn.addEventListener('click', e => {
                e.preventDefault();
                e.stopPropagation();
                this._closeAllDropdowns();
                menu.classList.toggle('show');
            });

            wrap.appendChild(btn);
            wrap.appendChild(menu);
            return wrap;
        }

        _closeAllDropdowns() {
            this.toolbar.querySelectorAll('.mublo-editor-dropdown-menu.show').forEach(m => m.classList.remove('show'));
        }

        _saveSelection() {
            const sel = window.getSelection();
            if (sel.rangeCount > 0) {
                this.savedRange = sel.getRangeAt(0);
            }
        }

        _restoreSelection() {
            this.contentArea.focus();
            if (this.savedRange) {
                const sel = window.getSelection();
                sel.removeAllRanges();
                sel.addRange(this.savedRange);
            }
        }

        _handleCommand(name, def) {
            this.contentArea.focus();
            switch (def.type) {
                case 'link': this._insertLink(); break;
                case 'image': this._openImageDialog(); break;
                case 'video': this._insertVideo(); break;
                case 'table': this._insertTable(); break;
                case 'fullscreen': this._toggleFullscreen(); break;
                case 'source': this._toggleSource(); break;
                case 'print': this._print(); break;
                case 'findreplace': this._toggleFindReplace(); break;
                default: this._exec(def.command, def.value);
            }
        }

        _exec(cmd, val = null) {
            this.contentArea.focus();
            document.execCommand(cmd, false, val);
            this._onChange();
        }

        // =========================================================
        // 모달 시스템
        // =========================================================
        _createModal(title, bodyHtml, primaryBtnText = '확인', onPrimaryClick = null) {
            const existingModal = document.getElementById('Mublo-modal');
            if (existingModal) existingModal.remove();

            const modal = document.createElement('div');
            modal.id = 'Mublo-modal';
            modal.className = 'Mublo-modal';
            modal.innerHTML = `
                <div class="Mublo-modal-backdrop"></div>
                <div class="Mublo-modal-dialog">
                    <div class="Mublo-modal-header">
                        <h5>${title}</h5>
                        <button type="button" class="Mublo-modal-close">&times;</button>
                    </div>
                    <div class="Mublo-modal-body">${bodyHtml}</div>
                    <div class="Mublo-modal-footer">
                        <div></div> <!-- Left side spacer -->
                        <div>
                            <button type="button" class="Mublo-modal-btn Mublo-modal-btn-secondary" id="Mublo-modal-cancel">취소</button>
                            <button type="button" class="Mublo-modal-btn Mublo-modal-btn-primary" id="Mublo-modal-confirm">${primaryBtnText}</button>
                        </div>
                    </div>
                </div>
            `;

            document.body.appendChild(modal);

            const closeBtn = modal.querySelector('.Mublo-modal-close');
            const cancelBtn = modal.querySelector('#Mublo-modal-cancel');
            const confirmBtn = modal.querySelector('#Mublo-modal-confirm');
            const backdrop = modal.querySelector('.Mublo-modal-backdrop');

            const closeModal = () => {
                modal.classList.add('Mublo-modal-closing');
                setTimeout(() => modal.remove(), 200);
                this._restoreSelection();
            };

            closeBtn.addEventListener('click', closeModal);
            cancelBtn.addEventListener('click', closeModal);
            backdrop.addEventListener('click', closeModal);

            if (onPrimaryClick) {
                confirmBtn.addEventListener('click', () => {
                    if (onPrimaryClick(modal) !== false) {
                        closeModal();
                    }
                });
            }

            // ESC 닫기
            const escHandler = (e) => {
                if (e.key === 'Escape') {
                    closeModal();
                    document.removeEventListener('keydown', escHandler);
                }
            };
            document.addEventListener('keydown', escHandler);

            // 첫 번째 입력창 포커스
            const firstInput = modal.querySelector('input, select, textarea');
            if (firstInput) setTimeout(() => firstInput.focus(), 50);

            return modal;
        }

        _insertLink() {
            this._saveSelection();
            const sel = window.getSelection();
            const text = sel.toString();
            
            const body = `
                <div class="Mublo-modal-form-group">
                    <label class="Mublo-modal-label">URL</label>
                    <input type="text" class="Mublo-modal-input" id="Mublo-link-url" value="https://" placeholder="https://example.com">
                </div>
                <div class="Mublo-modal-form-group">
                    <label class="Mublo-modal-label">표시할 텍스트</label>
                    <input type="text" class="Mublo-modal-input" id="Mublo-link-text" value="${escapeHtml(text)}">
                </div>
                <div class="Mublo-modal-check">
                    <input type="checkbox" id="Mublo-link-target" checked>
                    <label for="Mublo-link-target">새 탭에서 열기</label>
                </div>
            `;

            this._createModal('링크 삽입', body, '삽입', (modal) => {
                const url = modal.querySelector('#Mublo-link-url').value.trim();
                const label = modal.querySelector('#Mublo-link-text').value.trim();
                const target = modal.querySelector('#Mublo-link-target').checked ? '_blank' : '_self';

                if (!url || url === 'https://') return false;

                const html = `<a href="${escapeHtml(url)}" target="${target}">${escapeHtml(label || url)}</a>`;
                this._exec('insertHTML', html);
            });
        }

        _openImageDialog() {
            // 현재 커서 위치 저장 (모달이 열리면 포커스 소실)
            this._saveSelection();
            this._openImageModal();
        }

        _openImageModal() {
            // 기존 모달이 있으면 제거
            const existingModal = document.getElementById('Mublo-modal');
            if (existingModal) existingModal.remove();

            // 모달 생성
            const modal = document.createElement('div');
            modal.id = 'Mublo-modal';
            modal.className = 'Mublo-modal';
            modal.innerHTML = `
                <div class="Mublo-modal-backdrop"></div>
                <div class="Mublo-modal-dialog">
                    <div class="Mublo-modal-header">
                        <h5>이미지 추가</h5>
                        <button type="button" class="Mublo-modal-close">&times;</button>
                    </div>
                    <div class="Mublo-modal-body">
                        <div class="Mublo-image-upload-zone" id="Mublo-upload-zone">
                            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                                <rect x="3" y="3" width="18" height="18" rx="2"/>
                                <circle cx="8.5" cy="8.5" r="1.5"/>
                                <path d="M21 15l-5-5L5 21"/>
                            </svg>
                            <p>이미지를 드래그하거나 클릭하여 선택</p>
                            <p class="Mublo-image-upload-hint">여러 파일 선택 가능 (JPG, PNG, GIF, WebP)</p>
                            <input type="file" id="Mublo-image-input" accept="image/*" multiple hidden>
                        </div>
                        <div class="Mublo-image-url-input">
                            <input type="text" id="Mublo-image-url" placeholder="또는 이미지 URL 입력...">
                            <button type="button" id="Mublo-image-url-add">추가</button>
                        </div>
                        <div class="Mublo-image-preview-list" id="Mublo-preview-list">
                            <!-- 미리보기 이미지들이 여기에 추가됨 -->
                        </div>
                        <p class="Mublo-image-drag-hint" id="Mublo-drag-hint" style="display:none;">
                            드래그하여 순서를 변경할 수 있습니다
                        </p>
                    </div>
                    <div class="Mublo-modal-footer">
                        <span class="Mublo-image-count">선택된 이미지: <strong id="Mublo-image-count">0</strong>개</span>
                        <div>
                            <button type="button" class="Mublo-modal-btn Mublo-modal-btn-secondary" id="Mublo-image-cancel">취소</button>
                            <button type="button" class="Mublo-modal-btn Mublo-modal-btn-primary" id="Mublo-image-insert" disabled>삽입</button>
                        </div>
                    </div>
                </div>
            `;

            document.body.appendChild(modal);
            this._pendingImages = [];
            this._setupImageModal(modal);
        }

        _setupImageModal(modal) {
            const uploadZone = modal.querySelector('#Mublo-upload-zone');
            const fileInput = modal.querySelector('#Mublo-image-input');
            const urlInput = modal.querySelector('#Mublo-image-url');
            const urlAddBtn = modal.querySelector('#Mublo-image-url-add');
            const previewList = modal.querySelector('#Mublo-preview-list');
            const insertBtn = modal.querySelector('#Mublo-image-insert');
            const cancelBtn = modal.querySelector('#Mublo-image-cancel');
            const closeBtn = modal.querySelector('.Mublo-modal-close');
            const backdrop = modal.querySelector('.Mublo-modal-backdrop');
            const countEl = modal.querySelector('#Mublo-image-count');
            const dragHint = modal.querySelector('#Mublo-drag-hint');

            // 파일 선택
            uploadZone.addEventListener('click', () => fileInput.click());

            fileInput.addEventListener('change', () => {
                this._addFilesToPreview(Array.from(fileInput.files), previewList, countEl, insertBtn, dragHint);
                fileInput.value = '';
            });

            // 드래그 앤 드롭
            uploadZone.addEventListener('dragover', (e) => {
                e.preventDefault();
                uploadZone.classList.add('Mublo-image-upload-zone-active');
            });
            uploadZone.addEventListener('dragleave', () => {
                uploadZone.classList.remove('Mublo-image-upload-zone-active');
            });
            uploadZone.addEventListener('drop', (e) => {
                e.preventDefault();
                uploadZone.classList.remove('Mublo-image-upload-zone-active');
                const files = Array.from(e.dataTransfer.files).filter(f => f.type.startsWith('image/'));
                this._addFilesToPreview(files, previewList, countEl, insertBtn, dragHint);
            });

            // URL로 추가
            urlAddBtn.addEventListener('click', () => {
                const url = urlInput.value.trim();
                if (url) {
                    this._addUrlToPreview(url, previewList, countEl, insertBtn, dragHint);
                    urlInput.value = '';
                }
            });
            urlInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    urlAddBtn.click();
                }
            });

            // 닫기
            const closeModal = () => {
                modal.classList.add('Mublo-modal-closing');
                setTimeout(() => modal.remove(), 200);
                this._pendingImages = [];
            };
            closeBtn.addEventListener('click', closeModal);
            cancelBtn.addEventListener('click', closeModal);
            backdrop.addEventListener('click', closeModal);

            // 삽입
            insertBtn.addEventListener('click', async () => {
                insertBtn.disabled = true;
                insertBtn.textContent = '업로드 중...';

                for (const item of this._pendingImages) {
                    if (item.type === 'file') {
                        await this._handleImageUpload(item.file);
                    } else if (item.type === 'url') {
                        this.insertImage(item.url);
                    }
                }

                closeModal();
            });

            // ESC로 닫기
            const escHandler = (e) => {
                if (e.key === 'Escape') {
                    closeModal();
                    document.removeEventListener('keydown', escHandler);
                }
            };
            document.addEventListener('keydown', escHandler);

            // 드래그로 순서 변경
            this._setupPreviewDragSort(previewList);
        }

        _addFilesToPreview(files, previewList, countEl, insertBtn, dragHint) {
            files.forEach(file => {
                if (!file.type.startsWith('image/')) return;

                const reader = new FileReader();
                reader.onload = (e) => {
                    const id = 'img-' + Date.now() + '-' + Math.random().toString(36).substring(2, 11);
                    this._pendingImages.push({ id, type: 'file', file, preview: e.target.result });
                    this._renderPreviewItem(id, e.target.result, file.name, previewList, countEl, insertBtn, dragHint);
                };
                reader.readAsDataURL(file);
            });
        }

        _addUrlToPreview(url, previewList, countEl, insertBtn, dragHint) {
            const id = 'img-' + Date.now() + '-' + Math.random().toString(36).substring(2, 11);
            this._pendingImages.push({ id, type: 'url', url });
            this._renderPreviewItem(id, url, url.split('/').pop() || 'URL 이미지', previewList, countEl, insertBtn, dragHint);
        }

        _renderPreviewItem(id, src, name, previewList, countEl, insertBtn, dragHint) {
            const item = document.createElement('div');
            item.className = 'Mublo-image-preview-item';
            item.dataset.id = id;
            item.draggable = true;
            item.innerHTML = `
                <img src="${escapeHtml(src)}" alt="${escapeHtml(name)}">
                <span class="Mublo-image-preview-name" title="${escapeHtml(name)}">${escapeHtml(name.length > 20 ? name.substring(0, 17) + '...' : name)}</span>
                <button type="button" class="Mublo-image-preview-remove" title="제거">&times;</button>
                <span class="Mublo-image-preview-order">${this._pendingImages.length}</span>
            `;

            // 제거 버튼
            item.querySelector('.Mublo-image-preview-remove').addEventListener('click', (e) => {
                e.stopPropagation();
                this._pendingImages = this._pendingImages.filter(img => img.id !== id);
                item.remove();
                this._updatePreviewOrder(previewList);
                this._updateImageCount(countEl, insertBtn, dragHint);
            });

            previewList.appendChild(item);
            this._updateImageCount(countEl, insertBtn, dragHint);
        }

        _updateImageCount(countEl, insertBtn, dragHint) {
            const count = this._pendingImages.length;
            countEl.textContent = count;
            insertBtn.disabled = count === 0;
            dragHint.style.display = count > 1 ? 'block' : 'none';
        }

        _updatePreviewOrder(previewList) {
            const items = previewList.querySelectorAll('.Mublo-image-preview-item');
            items.forEach((item, index) => {
                item.querySelector('.Mublo-image-preview-order').textContent = index + 1;
            });
        }

        _setupPreviewDragSort(previewList) {
            let draggedItem = null;

            previewList.addEventListener('dragstart', (e) => {
                if (e.target.classList.contains('Mublo-image-preview-item')) {
                    draggedItem = e.target;
                    e.target.classList.add('Mublo-image-preview-dragging');
                    e.dataTransfer.effectAllowed = 'move';
                }
            });

            previewList.addEventListener('dragend', (e) => {
                if (e.target.classList.contains('Mublo-image-preview-item')) {
                    e.target.classList.remove('Mublo-image-preview-dragging');
                    draggedItem = null;
                }
            });

            previewList.addEventListener('dragover', (e) => {
                e.preventDefault();
                const afterElement = this._getDragAfterElement(previewList, e.clientY);
                if (draggedItem) {
                    if (afterElement == null) {
                        previewList.appendChild(draggedItem);
                    } else {
                        previewList.insertBefore(draggedItem, afterElement);
                    }
                }
            });

            previewList.addEventListener('drop', (e) => {
                e.preventDefault();
                // 순서 재정렬
                const newOrder = [];
                previewList.querySelectorAll('.Mublo-image-preview-item').forEach(item => {
                    const id = item.dataset.id;
                    const img = this._pendingImages.find(i => i.id === id);
                    if (img) newOrder.push(img);
                });
                this._pendingImages = newOrder;
                this._updatePreviewOrder(previewList);
            });
        }

        _getDragAfterElement(container, y) {
            const draggableElements = [...container.querySelectorAll('.Mublo-image-preview-item:not(.Mublo-image-preview-dragging)')];

            return draggableElements.reduce((closest, child) => {
                const box = child.getBoundingClientRect();
                const offset = y - box.top - box.height / 2;
                if (offset < 0 && offset > closest.offset) {
                    return { offset: offset, element: child };
                } else {
                    return closest;
                }
            }, { offset: Number.NEGATIVE_INFINITY }).element;
        }

        // =========================================================
        // 이미지 업로드 처리 (플러그인 지원)
        // =========================================================
        async _handleImageUpload(file) {
            // 파일 타입 체크
            if (!this.options.allowedImageTypes.includes(file.type)) {
                this.fire('uploadError', { error: '허용되지 않는 이미지 형식입니다.', file });
                alert('허용되지 않는 이미지 형식입니다.');
                return;
            }

            // 파일 크기 체크
            if (file.size > this.options.maxFileSize) {
                const maxMB = (this.options.maxFileSize / 1024 / 1024).toFixed(1);
                this.fire('uploadError', { error: `파일이 ${maxMB}MB를 초과합니다.`, file });
                alert(`파일이 ${maxMB}MB를 초과합니다.`);
                return;
            }

            // BlobInfo 생성
            const base64 = await fileToBase64(file);
            const blobInfo = new BlobInfo(file, base64);

            // 진행률 콜백
            const progress = (percent) => {
                this._showProgress(percent);
                this.fire('uploadProgress', { percent, blobInfo });
            };

            // 업로드 시작 이벤트
            this.fire('uploadStart', { blobInfo });

            try {
                let imageUrl;

                // 1. 플러그인에서 설정한 핸들러 (최우선)
                if (this._imageUploadHandler) {
                    imageUrl = await this._imageUploadHandler(blobInfo, progress);
                }
                // 2. 옵션으로 전달된 TinyMCE 스타일 핸들러
                else if (this.options.images_upload_handler) {
                    imageUrl = await new Promise((resolve, reject) => {
                        this.options.images_upload_handler(blobInfo, resolve, reject, progress);
                    });
                }
                // 3. 옵션으로 전달된 콜백 (하위 호환성)
                else if (this.options.onImageUpload) {
                    const result = await this.options.onImageUpload(file, this);
                    imageUrl = result?.url;
                }
                // 4. uploadUrl 설정된 경우 기본 업로드
                else if (this.options.uploadUrl) {
                    imageUrl = await this._defaultUpload(blobInfo, progress);
                }
                // 5. 폴백: Base64 인라인 (권장하지 않음)
                else {
                    console.warn('[MubloEditor] uploadUrl이 설정되지 않아 Base64로 삽입합니다. DB 저장 시 용량 문제가 발생할 수 있습니다. uploadUrl 옵션을 설정해주세요.');
                    imageUrl = `data:${file.type};base64,${base64}`;
                    this.fire('uploadWarning', {
                        message: 'Base64 fallback used. Consider setting uploadUrl option.',
                        blobInfo
                    });
                }

                if (imageUrl) {
                    this.insertImage(imageUrl, file.name);
                    this.fire('uploadSuccess', { url: imageUrl, blobInfo });
                }

            } catch (error) {
                console.error('[MubloEditor] Image upload failed:', error);
                this.fire('uploadError', { error: error.message || error, blobInfo });
                alert('이미지 업로드에 실패했습니다: ' + (error.message || error));
            } finally {
                this._hideProgress();
            }
        }

        async _defaultUpload(blobInfo, progress) {
            const formData = new FormData();
            formData.append('file', blobInfo.blob(), blobInfo.filename());

            const xhr = new XMLHttpRequest();
            
            return new Promise((resolve, reject) => {
                xhr.upload.addEventListener('progress', (e) => {
                    if (e.lengthComputable) {
                        progress(Math.round((e.loaded / e.total) * 100));
                    }
                });

                xhr.addEventListener('load', () => {
                    if (xhr.status >= 200 && xhr.status < 300) {
                        try {
                            const response = JSON.parse(xhr.responseText);
                            resolve(response.url || response.location || response.data?.url);
                        } catch (e) {
                            reject(new Error('Invalid server response'));
                        }
                    } else {
                        reject(new Error(`Upload failed: ${xhr.status}`));
                    }
                });

                xhr.addEventListener('error', () => reject(new Error('Upload failed')));
                xhr.addEventListener('abort', () => reject(new Error('Upload aborted')));

                xhr.open('POST', this.options.uploadUrl);
                
                if (this.options.images_upload_credentials) {
                    xhr.withCredentials = true;
                }

                xhr.send(formData);
            });
        }

        _showProgress(percent) {
            this.progressBar.style.display = 'block';
            this.progressBar.querySelector('.mublo-editor-progress-bar').style.width = percent + '%';
        }

        _hideProgress() {
            this.progressBar.style.display = 'none';
            this.progressBar.querySelector('.mublo-editor-progress-bar').style.width = '0%';
        }

        _insertVideo() {
            this._saveSelection();
            const body = `
                <div class="Mublo-modal-form-group">
                    <label class="Mublo-modal-label">동영상 URL (YouTube, Vimeo)</label>
                    <input type="text" class="Mublo-modal-input" id="Mublo-video-url" placeholder="https://www.youtube.com/watch?v=...">
                </div>
            `;

            this._createModal('동영상 삽입', body, '삽입', (modal) => {
                const url = modal.querySelector('#Mublo-video-url').value.trim();
                const embedUrl = this._parseVideoUrl(url);
                if (!embedUrl) {
                    alert('지원하지 않는 URL입니다.');
                    return false;
                }
                this.insertVideo(url);
            });
        }

        _parseVideoUrl(url) {
            // YouTube
            let match = url.match(/(?:youtube\.com\/(?:watch\?v=|embed\/)|youtu\.be\/)([a-zA-Z0-9_-]{11})/);
            if (match) {
                return `https://www.youtube.com/embed/${match[1]}`;
            }

            // Vimeo
            match = url.match(/(?:vimeo\.com\/)(\d+)/);
            if (match) {
                return `https://player.vimeo.com/video/${match[1]}`;
            }

            // 이미 embed URL인 경우
            if (url.includes('youtube.com/embed/') || url.includes('player.vimeo.com/')) {
                return url;
            }

            return null;
        }

        _insertTable() {
            this._saveSelection();
            const body = `
                <div class="Mublo-table-picker">
                    <div class="Mublo-table-grid" id="Mublo-table-grid"></div>
                    <div class="Mublo-table-info" id="Mublo-table-info">0 x 0</div>
                </div>
            `;

            const modal = this._createModal('테이블 삽입', body, '삽입', () => {
                // 그리드 클릭 시 이미 삽입되므로 확인 버튼은 닫기 역할만 하거나 비활성화
                return true;
            });

            // 그리드 생성 (10x10)
            const grid = modal.querySelector('#Mublo-table-grid');
            const info = modal.querySelector('#Mublo-table-info');
            
            for (let i = 0; i < 100; i++) {
                const cell = document.createElement('div');
                cell.className = 'Mublo-table-cell';
                cell.dataset.idx = i;
                grid.appendChild(cell);
            }

            const cells = grid.querySelectorAll('.Mublo-table-cell');
            
            grid.addEventListener('mouseover', (e) => {
                if (!e.target.classList.contains('Mublo-table-cell')) return;
                const idx = parseInt(e.target.dataset.idx);
                const row = Math.floor(idx / 10) + 1;
                const col = (idx % 10) + 1;
                info.textContent = `${row} x ${col}`;
                
                cells.forEach((c, i) => {
                    const r = Math.floor(i / 10) + 1;
                    const cIdx = (i % 10) + 1;
                    c.classList.toggle('active', r <= row && cIdx <= col);
                });
            });

            grid.addEventListener('click', () => {
                const [rows, cols] = info.textContent.split(' x ').map(Number);
                if (rows > 0 && cols > 0) {
                    let html = '<table class="table table-bordered" style="width:100%; border-collapse:collapse;"><tbody>';
                    for (let r = 0; r < rows; r++) {
                        html += '<tr>';
                        for (let c = 0; c < cols; c++) html += '<td style="border:1px solid #dee2e6; padding:8px;">&nbsp;</td>';
                        html += '</tr>';
                    }
                    html += '</tbody></table>';
                    this._exec('insertHTML', html);
                    modal.querySelector('.Mublo-modal-close').click();
                }
            });
        }

        _print() {
            const content = this.getHTML();
            const printWindow = window.open('', '_blank');
            printWindow.document.write(`
                <html>
                <head>
                    <title>Print</title>
                    <style>body{font-family:sans-serif;padding:20px;line-height:1.6}img{max-width:100%}</style>
                </head>
                <body>
                    ${content}
                    <script>window.onload=function(){window.print();window.close();}<\/script>
                </body>
                </html>
            `);
            printWindow.document.close();
        }

        _toggleFullscreen() {
            this.isFullscreen = !this.isFullscreen;
            this.wrapper.classList.toggle('mublo-editor-fullscreen', this.isFullscreen);
            document.body.classList.toggle('mublo-editor-noscroll', this.isFullscreen);
            const btn = this.toolbar.querySelector('[data-cmd="fullscreen"]');
            if (btn) btn.innerHTML = this.isFullscreen ? TOOLBAR_ITEMS.fullscreen.iconExit : TOOLBAR_ITEMS.fullscreen.icon;
            this.fire('fullscreenStateChanged', { state: this.isFullscreen });
        }

        _toggleSource() {
            this.isSourceMode = !this.isSourceMode;
            if (this.isSourceMode) {
                this.sourceArea.value = this._formatHTML(this.contentArea.innerHTML);
                this.contentArea.style.display = 'none';
                this.sourceArea.style.display = 'block';
            } else {
                const sourceValue = convertCodeShortcodesToHtml(this.sourceArea.value);
                this.contentArea.innerHTML = this.options.sanitize ? sanitizeHtml(sourceValue) : sourceValue;
                this.sourceArea.style.display = 'none';
                this.contentArea.style.display = 'block';
            }

            // 툴바 버튼 활성/비활성화 처리 (소스 모드에서는 편집 도구 잠금)
            this.toolbar.querySelectorAll('.mublo-editor-btn').forEach(btn => {
                const cmd = btn.dataset.cmd;
                if (cmd !== 'source' && cmd !== 'fullscreen') {
                    btn.disabled = this.isSourceMode;
                }
            });

            const btn = this.toolbar.querySelector('[data-cmd="source"]');
            if (btn) btn.classList.toggle('active', this.isSourceMode);
            this._onChange();
            this.fire('sourceModeChanged', { state: this.isSourceMode });
        }

        _formatHTML(html) {
            // 블록 태그 주위에 줄바꿈을 추가하여 가독성을 높임 (내용은 건드리지 않음)
            const tokens = html.split(/(<[^>]+>)/g);
            let formatted = '';
            const blockTags = ['p', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol', 'li', 'table', 'tbody', 'thead', 'tfoot', 'tr', 'td', 'th', 'blockquote', 'pre', 'hr', 'header', 'footer', 'section', 'article', 'aside', 'nav'];
            
            for (let i = 0; i < tokens.length; i++) {
                const token = tokens[i];
                if (!token) continue;
                
                const isTag = token.startsWith('<') && token.endsWith('>');
                if (isTag) {
                    const tagNameMatch = token.match(/^<\/?([a-z0-9]+)/i);
                    const tagName = tagNameMatch ? tagNameMatch[1].toLowerCase() : '';
                    const isBlock = blockTags.includes(tagName);
                    
                    if (isBlock) {
                        const isClosing = token.startsWith('</');
                        if (!isClosing) {
                            // 여는 태그: 앞에 줄바꿈
                            if (formatted.length > 0 && !formatted.endsWith('\n')) formatted += '\n';
                            formatted += token;
                        } else {
                            // 닫는 태그: 뒤에 줄바꿈
                            formatted += token;
                            if (i < tokens.length - 1) formatted += '\n';
                        }
                    } else {
                        formatted += token;
                    }
                } else {
                    formatted += token;
                }
            }
            
            // 연속된 줄바꿈 제거 및 정리
            return formatted.replace(/\n\s*\n/g, '\n').trim();
        }

        // =========================================================
        // 찾기/바꾸기
        // =========================================================
        _toggleFindReplace() {
            if (this.findReplaceBar && this.findReplaceBar.style.display !== 'none') {
                this._closeFindReplace();
                return;
            }
            this._openFindReplace();
        }

        _openFindReplace() {
            if (!this.findReplaceBar) {
                this._buildFindReplaceBar();
            }
            this.findReplaceBar.style.display = 'flex';
            this.findReplaceBar.querySelector('.mublo-editor-find-input').focus();
            const btn = this.toolbar.querySelector('[data-cmd="findreplace"]');
            if (btn) btn.classList.add('active');
        }

        _closeFindReplace() {
            if (this.findReplaceBar) {
                this.findReplaceBar.style.display = 'none';
            }
            this._clearHighlights();
            const btn = this.toolbar.querySelector('[data-cmd="findreplace"]');
            if (btn) btn.classList.remove('active');
        }

        _buildFindReplaceBar() {
            this.findReplaceBar = document.createElement('div');
            this.findReplaceBar.className = 'mublo-editor-findreplace';
            this.findReplaceBar.innerHTML = `
                <input type="text" class="mublo-editor-find-input" placeholder="찾기...">
                <input type="text" class="mublo-editor-replace-input" placeholder="바꾸기...">
                <span class="mublo-editor-find-count"></span>
                <button type="button" class="mublo-editor-btn mublo-editor-find-prev" title="이전">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="18 15 12 9 6 15"/></svg>
                </button>
                <button type="button" class="mublo-editor-btn mublo-editor-find-next" title="다음">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"/></svg>
                </button>
                <button type="button" class="mublo-editor-btn mublo-editor-replace-one" title="바꾸기">바꾸기</button>
                <button type="button" class="mublo-editor-btn mublo-editor-replace-all" title="모두 바꾸기">모두</button>
                <button type="button" class="mublo-editor-btn mublo-editor-find-close" title="닫기">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                </button>
            `;

            // 이벤트 바인딩
            const findInput = this.findReplaceBar.querySelector('.mublo-editor-find-input');
            const replaceInput = this.findReplaceBar.querySelector('.mublo-editor-replace-input');

            findInput.addEventListener('input', () => this._doFind(findInput.value));
            findInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    this._findNext();
                }
                if (e.key === 'Escape') {
                    this._closeFindReplace();
                }
            });

            replaceInput.addEventListener('keydown', (e) => {
                if (e.key === 'Escape') {
                    this._closeFindReplace();
                }
            });

            this.findReplaceBar.querySelector('.mublo-editor-find-prev').addEventListener('click', () => this._findPrev());
            this.findReplaceBar.querySelector('.mublo-editor-find-next').addEventListener('click', () => this._findNext());
            this.findReplaceBar.querySelector('.mublo-editor-replace-one').addEventListener('click', () => this._replaceOne());
            this.findReplaceBar.querySelector('.mublo-editor-replace-all').addEventListener('click', () => this._replaceAll());
            this.findReplaceBar.querySelector('.mublo-editor-find-close').addEventListener('click', () => this._closeFindReplace());

            this.toolbar.parentNode.insertBefore(this.findReplaceBar, this.toolbar.nextSibling);
            this._findMatches = [];
            this._currentMatchIndex = -1;
        }

        _doFind(query) {
            this._clearHighlights();
            this._findMatches = [];
            this._currentMatchIndex = -1;

            const countEl = this.findReplaceBar.querySelector('.mublo-editor-find-count');

            if (!query || query.length < 1) {
                countEl.textContent = '';
                return;
            }

            // 텍스트 노드에서 찾기
            const walker = document.createTreeWalker(this.contentArea, NodeFilter.SHOW_TEXT, null, false);
            const textNodes = [];
            while (walker.nextNode()) {
                textNodes.push(walker.currentNode);
            }

            textNodes.forEach(node => {
                const nodeText = node.textContent;
                let localMatch;
                const localRegex = new RegExp(query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi');
                while ((localMatch = localRegex.exec(nodeText)) !== null) {
                    this._findMatches.push({
                        node: node,
                        index: localMatch.index,
                        length: localMatch[0].length,
                        text: localMatch[0]
                    });
                }
            });

            countEl.textContent = this._findMatches.length > 0 ? `${this._findMatches.length}개 발견` : '결과 없음';

            if (this._findMatches.length > 0) {
                this._currentMatchIndex = 0;
                this._highlightMatch(0);
            }
        }

        _highlightMatch(index) {
            this._clearHighlights();
            if (index < 0 || index >= this._findMatches.length) return;

            const match = this._findMatches[index];
            const range = document.createRange();
            range.setStart(match.node, match.index);
            range.setEnd(match.node, match.index + match.length);

            const highlight = document.createElement('span');
            highlight.className = 'mublo-editor-highlight';
            range.surroundContents(highlight);

            highlight.scrollIntoView({ behavior: 'smooth', block: 'center' });

            const countEl = this.findReplaceBar.querySelector('.mublo-editor-find-count');
            countEl.textContent = `${index + 1} / ${this._findMatches.length}`;
        }

        _clearHighlights() {
            this.contentArea.querySelectorAll('.mublo-editor-highlight').forEach(el => {
                const parent = el.parentNode;
                while (el.firstChild) {
                    parent.insertBefore(el.firstChild, el);
                }
                parent.removeChild(el);
            });
            // 인접 텍스트 노드 병합
            this.contentArea.normalize();
        }

        _findNext() {
            if (this._findMatches.length === 0) return;
            // 검색 다시 실행 (하이라이트가 DOM을 변경하므로)
            const query = this.findReplaceBar.querySelector('.mublo-editor-find-input').value;
            this._clearHighlights();
            this._doFindWithoutHighlight(query);
            this._currentMatchIndex = (this._currentMatchIndex + 1) % this._findMatches.length;
            this._highlightMatch(this._currentMatchIndex);
        }

        _findPrev() {
            if (this._findMatches.length === 0) return;
            const query = this.findReplaceBar.querySelector('.mublo-editor-find-input').value;
            this._clearHighlights();
            this._doFindWithoutHighlight(query);
            this._currentMatchIndex = (this._currentMatchIndex - 1 + this._findMatches.length) % this._findMatches.length;
            this._highlightMatch(this._currentMatchIndex);
        }

        _doFindWithoutHighlight(query) {
            this._findMatches = [];
            if (!query) return;

            const walker = document.createTreeWalker(this.contentArea, NodeFilter.SHOW_TEXT, null, false);
            const textNodes = [];
            while (walker.nextNode()) {
                textNodes.push(walker.currentNode);
            }

            textNodes.forEach(node => {
                const nodeText = node.textContent;
                const localRegex = new RegExp(query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi');
                let localMatch;
                while ((localMatch = localRegex.exec(nodeText)) !== null) {
                    this._findMatches.push({
                        node: node,
                        index: localMatch.index,
                        length: localMatch[0].length,
                        text: localMatch[0]
                    });
                }
            });
        }

        _replaceOne() {
            const findInput = this.findReplaceBar.querySelector('.mublo-editor-find-input');
            const replaceInput = this.findReplaceBar.querySelector('.mublo-editor-replace-input');
            const query = findInput.value;
            const replacement = replaceInput.value;

            if (!query || this._findMatches.length === 0) return;

            this._clearHighlights();
            this._doFindWithoutHighlight(query);

            if (this._currentMatchIndex >= 0 && this._currentMatchIndex < this._findMatches.length) {
                const match = this._findMatches[this._currentMatchIndex];
                const range = document.createRange();
                range.setStart(match.node, match.index);
                range.setEnd(match.node, match.index + match.length);
                range.deleteContents();
                range.insertNode(document.createTextNode(replacement));
                this.contentArea.normalize();
                this._onChange();
            }

            this._doFind(query);
        }

        _replaceAll() {
            const findInput = this.findReplaceBar.querySelector('.mublo-editor-find-input');
            const replaceInput = this.findReplaceBar.querySelector('.mublo-editor-replace-input');
            const query = findInput.value;
            const replacement = replaceInput.value;

            if (!query) return;

            this._clearHighlights();

            // innerHTML에서 직접 치환 (텍스트만)
            const walker = document.createTreeWalker(this.contentArea, NodeFilter.SHOW_TEXT, null, false);
            const textNodes = [];
            while (walker.nextNode()) {
                textNodes.push(walker.currentNode);
            }

            const regex = new RegExp(query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi');
            let count = 0;

            textNodes.forEach(node => {
                const original = node.textContent;
                const replaced = original.replace(regex, () => {
                    count++;
                    return replacement;
                });
                if (original !== replaced) {
                    node.textContent = replaced;
                }
            });

            this._onChange();
            this._doFind(query);

            const countEl = this.findReplaceBar.querySelector('.mublo-editor-find-count');
            countEl.textContent = `${count}개 바꿈`;
        }

        _bindEvents() {
            this.contentArea.addEventListener('input', () => this._onChange());
            this.contentArea.addEventListener('focus', () => {
                this.wrapper.classList.add('focused');
                this._ensureParagraphSeparator();
                this.options.onFocus?.(this);
                this.fire('focus');
            });
            this.contentArea.addEventListener('blur', () => {
                this.wrapper.classList.remove('focused');
                this.sync();
                this.options.onBlur?.(this);
                this.fire('blur');
            });
            this.contentArea.addEventListener('keydown', e => this._onKeydown(e));
            this.contentArea.addEventListener('paste', e => this._onPaste(e));
            this.contentArea.addEventListener('drop', e => this._onDrop(e));
            this.contentArea.addEventListener('dragover', e => e.preventDefault());
            
            // 전역 클릭 핸들러 (드롭다운 닫기)
            this._handlers.docClick = (e) => {
                if (this.toolbar && !this.toolbar.contains(e.target)) this._closeAllDropdowns();
            };
            document.addEventListener('click', this._handlers.docClick);

            if (this.options.autofocus) setTimeout(() => this.focus(), 100);
            this._updateWordCount();
            this._initAutosave();
            this._initImageResizer();
            this._initMarkdownShortcuts();
            this.options.onReady?.(this);
        }

        // =========================================================
        // 자동 저장
        // =========================================================
        _getAutosaveKey() {
            return this.options.autosaveKey || `mublo-editor-autosave-${this.id}`;
        }

        _initAutosave() {
            if (!this.options.autosave) return;

            // 저장된 내용 복원
            if (this.options.autosaveRestore) {
                const saved = this.getAutosavedContent();
                if (saved && saved.content && !this.originalElement.value) {
                    const restore = confirm(`저장된 내용이 있습니다. (${new Date(saved.timestamp).toLocaleString()})\n복원하시겠습니까?`);
                    if (restore) {
                        this.setHTML(saved.content);
                    }
                }
            }

            // 주기적 자동 저장 시작
            this._startAutosave();
        }

        _startAutosave() {
            if (!this.options.autosave || this._autosaveTimer) return;

            this._autosaveTimer = setInterval(() => {
                this._doAutosave();
            }, this.options.autosaveInterval);
        }

        _stopAutosave() {
            if (this._autosaveTimer) {
                clearInterval(this._autosaveTimer);
                this._autosaveTimer = null;
            }
        }

        _doAutosave() {
            if (this.isEmpty()) return;

            const key = this._getAutosaveKey();
            const data = {
                content: this.getHTML(),
                timestamp: Date.now(),
                id: this.id
            };

            try {
                localStorage.setItem(key, JSON.stringify(data));
                this.fire('autosave', data);
            } catch (e) {
                console.error('[MubloEditor] Autosave failed:', e);
                this.fire('autosaveError', { error: e.message });
            }
        }

        getAutosavedContent() {
            const key = this._getAutosaveKey();
            try {
                const data = localStorage.getItem(key);
                return data ? JSON.parse(data) : null;
            } catch (e) {
                return null;
            }
        }

        clearAutosave() {
            const key = this._getAutosaveKey();
            localStorage.removeItem(key);
            this.fire('autosaveClear');
            return this;
        }

        saveNow() {
            this._doAutosave();
            return this;
        }

        _onKeydown(e) {
            const mod = navigator.platform.includes('Mac') ? e.metaKey : e.ctrlKey;
            if (mod) {
                const key = e.key.toLowerCase();
                if (key === 'b') { e.preventDefault(); this._exec('bold'); }
                if (key === 'i') { e.preventDefault(); this._exec('italic'); }
                if (key === 'u') { e.preventDefault(); this._exec('underline'); }
                if (key === 'k') { e.preventDefault(); this._insertLink(); }
                if (key === 'f') { e.preventDefault(); this._openFindReplace(); }
                if (key === 'h') { e.preventDefault(); this._openFindReplace(); }
                if (key === 'z') { e.preventDefault(); this._exec(e.shiftKey ? 'redo' : 'undo'); }
                if (key === 'y') { e.preventDefault(); this._exec('redo'); }
            }
            if (e.key === 'Tab') {
                e.preventDefault();
                this._exec(e.shiftKey ? 'outdent' : 'indent');
            }
            this.fire('keydown', { originalEvent: e });
        }

        // =========================================================
        // 마크다운 단축키
        // =========================================================
        _initMarkdownShortcuts() {
            this.contentArea.addEventListener('keyup', (e) => {
                if (e.key === ' ' || e.key === 'Enter') {
                    this._checkMarkdown(e);
                }
            });
        }

        _checkMarkdown(e) {
            const sel = window.getSelection();
            if (!sel.isCollapsed) return;

            const node = sel.anchorNode;
            if (node.nodeType !== 3) return; // 텍스트 노드만 처리

            const text = node.textContent;
            const offset = sel.anchorOffset;
            // 입력된 문자 바로 앞까지의 텍스트 확인
            const prefix = text.substring(0, offset).trim(); 

            // 패턴 매칭
            let cmd = null;
            let val = null;

            if (e.key === ' ') {
                if (prefix === '#') { cmd = 'formatBlock'; val = 'h1'; removeLen = 1; }
                else if (prefix === '##') { cmd = 'formatBlock'; val = 'h2'; removeLen = 2; }
                else if (prefix === '###') { cmd = 'formatBlock'; val = 'h3'; removeLen = 3; }
                else if (prefix === '-') { cmd = 'insertUnorderedList'; removeLen = 1; }
                else if (prefix === '*') { cmd = 'insertUnorderedList'; removeLen = 1; }
                else if (prefix === '1.') { cmd = 'insertOrderedList'; removeLen = 2; }
                else if (prefix === '>') { cmd = 'formatBlock'; val = 'blockquote'; removeLen = 1; }
            } else if (e.key === 'Enter') {
                // --- 입력 후 엔터 시 수평선
                // 엔터 키 입력 시점에는 이미 줄바꿈이 일어났을 수 있으므로 이전 줄 확인 필요
                // 여기서는 간단히 현재 블록의 텍스트가 '---' 인지 확인하는 방식보다는
                // keyup 이벤트라 이미 줄바꿈 된 상태일 수 있어 처리가 복잡할 수 있음.
                // 간단하게 '---' 감지는 생략하거나 input 이벤트에서 처리 권장.
            }

            if (cmd) {
                // 마크다운 문법 문자 제거
                const range = document.createRange();
                range.setStart(node, 0);
                range.setEnd(node, offset);
                range.deleteContents();

                this._exec(cmd, val);
                e.preventDefault();
            }
        }

        // =========================================================
        // 이미지 리사이저
        // =========================================================
        _initImageResizer() {
            // 이미지 클릭 시 리사이저 표시
            this.contentArea.addEventListener('click', (e) => {
                if (e.target.tagName === 'IMG') {
                    this._selectImage(e.target);
                } else {
                    this._hideResizer();
                }
            });

            // 스크롤 시 리사이저 위치 업데이트
            this.contentArea.addEventListener('scroll', () => this._updateResizerPosition());
            
            // 윈도우 리사이즈 핸들러
            this._handlers.winResize = () => this._updateResizerPosition();
            window.addEventListener('resize', this._handlers.winResize);

            // 핸들 드래그
            let startX, startY, startWidth, startHeight, activeHandle;

            const onMouseMove = (e) => {
                if (!activeHandle || !this._selectedImage) return;
                e.preventDefault();
                
                const dx = e.clientX - startX;
                const dy = e.clientY - startY;
                
                let newWidth = startWidth;
                let newHeight = startHeight;

                // 비율 유지하며 크기 조절 (간단하게 가로 기준)
                if (activeHandle.classList.contains('Mublo-resizer-se') || activeHandle.classList.contains('Mublo-resizer-ne')) {
                    newWidth = startWidth + dx;
                } else {
                    newWidth = startWidth - dx;
                }

                if (newWidth > 20) {
                    this._selectedImage.style.width = newWidth + 'px';
                    this._selectedImage.style.height = 'auto'; // 비율 유지
                    this._updateResizerPosition();
                }
            };

            const onMouseUp = () => {
                activeHandle = null;
                document.removeEventListener('mousemove', onMouseMove);
                document.removeEventListener('mouseup', onMouseUp);
                this._onChange(); // 변경 사항 저장
            };

            this._resizer.addEventListener('mousedown', (e) => {
                if (e.target.classList.contains('Mublo-resizer-handle')) {
                    e.preventDefault();
                    activeHandle = e.target;
                    startX = e.clientX;
                    startY = e.clientY;
                    startWidth = this._selectedImage.offsetWidth;
                    startHeight = this._selectedImage.offsetHeight;

                    document.addEventListener('mousemove', onMouseMove);
                    document.addEventListener('mouseup', onMouseUp);
                }
            });
        }

        _selectImage(img) {
            this._selectedImage = img;
            this._resizer.classList.add('active');
            this._updateResizerPosition();
        }

        _hideResizer() {
            this._selectedImage = null;
            this._resizer.classList.remove('active');
        }

        _updateResizerPosition() {
            if (!this._selectedImage) return;

            const imgRect = this._selectedImage.getBoundingClientRect();
            const wrapperRect = this.wrapper.getBoundingClientRect();

            // wrapper 기준 상대 좌표 계산
            const top = imgRect.top - wrapperRect.top;
            const left = imgRect.left - wrapperRect.left;

            this._resizer.style.top = top + 'px';
            this._resizer.style.left = left + 'px';
            this._resizer.style.width = imgRect.width + 'px';
            this._resizer.style.height = imgRect.height + 'px';
        }

        _onPaste(e) {
            const items = e.clipboardData?.items;
            if (items && this.options.automatic_uploads) {
                for (const item of items) {
                    if (item.type.startsWith('image/')) {
                        e.preventDefault();
                        this._handleImageUpload(item.getAsFile());
                        return;
                    }
                }
            }
            if (this.options.sanitize) {
                const html = e.clipboardData?.getData('text/html');
                if (html) {
                    e.preventDefault();
                    this._exec('insertHTML', sanitizeHtml(html));
                }
            }
            this.fire('paste', { originalEvent: e });
        }

        _onDrop(e) {
            const files = e.dataTransfer?.files;
            if (files && this.options.automatic_uploads) {
                for (const file of files) {
                    if (file.type.startsWith('image/')) {
                        e.preventDefault();
                        this._handleImageUpload(file);
                    }
                }
            }
            this.fire('drop', { originalEvent: e });
        }

        _onChange() {
            this.sync();
            this._updateWordCount();
            this.options.onChange?.(this.getHTML(), this);
            this.fire('change', { content: this.getHTML() });
        }

        _updateWordCount() {
            if (!this.options.showWordCount || !this.statusBar) return;

            const text = this.getText();
            const chars = text.length;
            const charsNoSpace = text.replace(/\s/g, '').length;
            const words = text.trim() ? text.trim().split(/\s+/).length : 0;

            let html = `글자: ${chars}`;
            if (this.options.maxLength > 0) {
                html += ` / ${this.options.maxLength}`;
                if (chars > this.options.maxLength) {
                    html = `<span class="mublo-editor-over-limit">${html}</span>`;
                }
            }
            html += ` | 공백 제외: ${charsNoSpace} | 단어: ${words}`;

            this.statusBar.querySelector('.mublo-editor-wordcount').innerHTML = html;
            this.fire('wordcount', { chars, charsNoSpace, words, maxLength: this.options.maxLength });
        }

        _initPlugins() {
            plugins.forEach((fn, name) => {
                try { fn(this); } catch (e) { console.error(`Plugin ${name} error:`, e); }
            });
        }

        // =========================================================
        // Public API
        // =========================================================
        getHTML() { 
            const html = this.isSourceMode ? this.sourceArea.value : this.contentArea.innerHTML;
            return this._formatHTML(convertCodeShortcodesToHtml(html));
        }
        
        setHTML(html) {
            let safe = this.options.sanitize ? sanitizeHtml(html) : html;
            safe = convertCodeShortcodesToHtml(safe);
            
            // 1. 내용이 없으면 기본 P 태그 삽입 (첫 줄 div 방지)
            if (!safe && !this.options.readonly) {
                safe = '<p><br></p>';
            } else if (!this.options.readonly) {
                // 2. 내용이 블록 태그로 시작하지 않으면 <p>로 감싸기 (평문 초기화 대응)
                const trimmed = safe.trim();
                const blockTags = ['<p', '<div', '<h1', '<h2', '<h3', '<h4', '<h5', '<h6', '<ul', '<ol', '<table', '<blockquote', '<pre', '<hr'];
                const startsWithBlock = blockTags.some(tag => trimmed.toLowerCase().startsWith(tag));
                
                if (!startsWithBlock) {
                    safe = `<p>${safe}</p>`;
                }
            }
            this.contentArea.innerHTML = safe;
            this.sourceArea.value = safe;
            this.sync();
            return this;
        }
        
        getText() { return this.contentArea.textContent || ''; }
        isEmpty() { return !this.getText().trim(); }

        getWordCount() {
            const text = this.getText();
            return {
                chars: text.length,
                charsNoSpace: text.replace(/\s/g, '').length,
                words: text.trim() ? text.trim().split(/\s+/).length : 0
            };
        }
        focus() { (this.isSourceMode ? this.sourceArea : this.contentArea).focus(); return this; }
        blur() { (this.isSourceMode ? this.sourceArea : this.contentArea).blur(); return this; }
        sync() { this.originalElement.value = this.getHTML(); return this; }

        setReadonly(readonly) {
            this.options.readonly = readonly;
            this.contentArea.contentEditable = !readonly;
            this.sourceArea.readOnly = readonly;
            this.wrapper.classList.toggle('mublo-editor-readonly', readonly);

            // 툴바 버튼 비활성화
            this.toolbar.querySelectorAll('.mublo-editor-btn').forEach(btn => {
                btn.disabled = readonly;
            });

            this.fire('readonlyStateChanged', { state: readonly });
            return this;
        }

        isReadonly() {
            return this.options.readonly;
        }

        enable() { return this.setReadonly(false); }
        disable() { return this.setReadonly(true); }
        
        insertContent(html) {
            this._restoreSelection();
            this._exec('insertHTML', html);
            return this;
        }

        insertImage(url, alt = '') {
            const html = `<img src="${escapeHtml(url)}" alt="${escapeHtml(alt)}" style="max-width:100%">`;
            return this.insertContent(html);
        }

        insertVideo(url) {
            const embedUrl = this._parseVideoUrl(url);
            if (!embedUrl) {
                console.error('[MubloEditor] Invalid video URL:', url);
                return this;
            }
            const html = `<div class="mublo-editor-video-wrapper" contenteditable="false">
                <iframe src="${escapeHtml(embedUrl)}" frameborder="0" allowfullscreen allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"></iframe>
            </div>`;
            return this.insertContent(html);
        }

        destroy() {
            this.fire('destroy');
            this._stopAutosave();
            this.originalElement.style.display = '';
            
            // 전역 리스너 제거
            if (this._handlers.docClick) document.removeEventListener('click', this._handlers.docClick);
            if (this._handlers.winResize) window.removeEventListener('resize', this._handlers.winResize);
            
            this.wrapper.remove();
            instances.delete(this.id);
            if (this.isFullscreen) document.body.classList.remove('mublo-editor-noscroll');
            this._eventListeners.clear();
        }
        
        getElement() { return this.contentArea; }
        getWrapper() { return this.wrapper; }
        getToolbar() { return this.toolbar; }
    }

    // =========================================================
    // 자동 초기화
    // =========================================================
    function autoInit() {
        document.querySelectorAll(`.${EDITOR_CLASS}`).forEach(el => {
            if (!instances.has(el.id || el)) new Editor(el);
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', autoInit);
    } else {
        autoInit();
    }

    // =========================================================
    // Public API
    // =========================================================
    return {
        VERSION,
        
        create(selector, options = {}) {
            const el = typeof selector === 'string' ? document.querySelector(selector) : selector;
            if (!el) { console.error('[MubloEditor] Element not found:', selector); return null; }
            if (el.id && instances.has(el.id)) return instances.get(el.id);
            return new Editor(el, options);
        },
        
        get(id) { return instances.get(id) || null; },
        getAll() { return Array.from(instances.values()); },
        destroy(id) { instances.get(id)?.destroy(); },
        destroyAll() { instances.forEach(e => e.destroy()); },
        
        registerPlugin(name, fn) {
            if (typeof fn !== 'function') return false;
            plugins.set(name, fn);
            // 이미 생성된 에디터에도 적용
            instances.forEach(e => { try { fn(e); } catch (err) { console.error(err); } });
            return true;
        },
        
        syncAll() { instances.forEach(e => e.sync()); },
        
        // 상수 노출
        TOOLBAR_ITEMS,
        TOOLBAR_PRESETS,
        DEFAULT_COLORS,
        BlobInfo
    };
})();

if (typeof module !== 'undefined' && module.exports) module.exports = MubloEditor;
