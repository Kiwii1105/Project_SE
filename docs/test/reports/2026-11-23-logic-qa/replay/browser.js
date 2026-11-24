(() => {
  "use strict";

  const qa = window.eduMateQa;
  const send = window.fetch.bind(window);
  const requests = [];
  window.fetch = async (url, options = {}) => {
    if (typeof url !== "string" || !url.startsWith("/api/")) return send(url, options);
    const headers = new Headers(options.headers);
    headers.set("X-EduMate-QA-Run", qa.token);
    const entry = { path: url.split("?")[0], method: options.method || "GET", status: null };
    requests.push(entry);
    try {
      const response = await send(url, { ...options, headers });
      entry.status = response.status;
      return response;
    } catch (error) {
      entry.status = "hủy";
      throw error;
    }
  };

  const find = (selector, parent = document) => parent.querySelector(selector);
  const text = (selector, parent = document) => find(selector, parent)?.textContent.trim() || "";
  const pause = ms => new Promise(resolve => setTimeout(resolve, ms));

  async function waitFor(read, description) {
    const deadline = Date.now() + 9000;
    let result = read();
    while (!result && Date.now() < deadline) {
      await pause(25);
      result = read();
    }
    if (!result) throw new Error(`Không thấy ${description} trong thời gian chờ.`);
    return result;
  }

  async function selectTab(name, expected) {
    const button = await waitFor(() => find(`#tabs [data-tab="${name}"]`), `tab ${name}`);
    button.click();
    return waitFor(() => find(expected), `nội dung tab ${name}`);
  }

  async function completed(path, method = "POST") {
    const matches = () => requests.filter(call => call.path === path && call.method === method);
    await waitFor(() => matches().length > 0 && matches().every(call => call.status !== null),
                  `phản hồi ${method} ${path}`);
    await pause(80); // Let EduMate apply the response to its DOM.
    return matches().map(call => call.status);
  }

  function courseCard() {
    return Array.from(document.querySelectorAll("#content .course-card"))
      .find(card => find(`[data-id="${qa.courseId}"]`, card));
  }

  async function management(formName) {
    await selectTab("courses", "#content .course-card");
    const card = await waitFor(courseCard, "thẻ môn mẫu");
    const details = find("details", card);
    if (!details) throw new Error("Không thấy khung quản lý môn.");
    if (!details.open) find("summary", details).click();
    return waitFor(() => find(`form[data-submit="${formName}"]`, details), `form ${formName}`);
  }

  function result(reproduced, facts) {
    return { reproduced, facts };
  }

  const replay = {
    async "QA-07"() {
      await selectTab("qa", "#content .qa-toolbar");
      const status = await waitFor(() => text(".qa-toolbar .badge"), "chỉ báo câu hỏi");
      const replyVisible = text(".ans .pre").includes("Em bổ sung nội dung");
      if (!replyVisible) throw new Error("Không thấy phản hồi mẫu của sinh viên.");
      return result(status === "Đã trả lời hết", {
        "Ai đã phản hồi": "Sinh viên QA. Giảng viên chưa phản hồi.",
        "Chỉ báo trên giao diện": status,
        "Quy tắc cần đối chiếu": "BR-09. Chỉ phản hồi của giảng viên mới đổi trạng thái.",
      });
    },

    async "QA-08"() {
      const form = await management("addDeadline");
      const name = "Kỳ thi minh chứng QA-08";
      form.elements.title.value = name;
      form.elements.kind.value = "exam";
      form.elements.due_at.value = qa.futureDate;
      form.requestSubmit(find('button', form));
      const path = `/api/courses/${qa.courseId}/deadlines`;
      const statuses = await completed(path);
      if (statuses.at(-1) !== 201) throw new Error("Không tạo được kỳ thi mẫu.");
      const listItem = await waitFor(() => Array.from(document.querySelectorAll("#content li"))
        .find(item => item.textContent.includes(name)), "kỳ thi vừa tạo");
      const toast = text("#toast");
      return result(toast === "Đã thêm bài tập" && text(".tag", listItem) === "Kỳ thi", {
        "Loại lưu trong môn học": text(".tag", listItem),
        "Thông báo vừa hiện": toast,
        "Kỳ vọng": "Thông báo gọi đúng loại là kỳ thi.",
      });
    },

    async "QA-09"() {
      await selectTab("courses", "#content .course-card");
      find('#tabs [data-tab="qa"]').click();
      await waitFor(() => requests.some(call => call.path === "/api/questions"), "yêu cầu Hỏi đáp");
      await selectTab("timetable", "#content .week");
      const statuses = await completed("/api/questions", "GET");
      const stillWeek = find('#tabs [data-tab="timetable"]').getAttribute("aria-pressed") === "true";
      const showsQa = Boolean(find("#content .qa-compose"));
      return result(stillWeek && showsQa, {
        "Tab đang chọn": stillWeek ? "Thời khóa biểu" : "Đã đổi tab",
        "Nội dung cuối": showsQa ? "Đặt câu hỏi" : find("#content .week") ? "Thời khóa biểu" : "Khác",
        "Phản hồi Hỏi đáp": statuses.join(", "),
        "Điều kiện": "Mô phỏng Hỏi đáp phản hồi chậm 1,5 giây.",
      });
    },

    async "QA-11"() {
      const box = () => find(`input[data-id="${qa.deadlineId}"][type="checkbox"]`);
      await selectTab("deadlines", `input[data-id="${qa.deadlineId}"]`);
      box().click();
      await pause(150);
      box().click();
      const afterClick = box().checked;
      const statuses = await completed(`/api/deadlines/${qa.deadlineId}/done`);
      const checked = await waitFor(box, "ô hoàn thành").then(input => input.checked);
      return result(!afterClick && checked, {
        "Ngay sau thao tác bỏ tick": afterClick ? "Còn dấu tick" : "Ô trống",
        "Sau khi các yêu cầu xử lý xong": checked ? "Có dấu tick" : "Ô trống",
        "Số phản hồi": statuses.length,
        "Điều kiện": "Mô phỏng lần lưu dấu tick phản hồi chậm 1,8 giây.",
      });
    },

    async "QA-12"() {
      await selectTab("courses", "#content .course-card");
      const card = await waitFor(courseCard, "môn thử đăng ký");
      const enroll = find('[data-click="enroll"]', card);
      if (!enroll) throw new Error("Không thấy nút Đăng ký của môn mẫu.");
      enroll.click();
      enroll.click();
      const statuses = await completed(`/api/courses/${qa.courseId}/enroll`);
      const registered = Boolean(find('[data-click="unenroll"]', courseCard()));
      const toast = text("#toast");
      return result(registered && statuses.includes(201) && statuses.includes(409), {
        "Trạng thái môn": registered ? "Đã đăng ký" : "Chưa đăng ký",
        "HTTP từ thao tác bấm đúp": statuses.join(", "),
        "Thông báo cuối": toast,
        "Kỳ vọng": "Một lần đăng ký đang xử lý chỉ gửi một yêu cầu.",
      });
    },

    async "QA-13"() {
      const form = await management("addSession");
      form.elements.weekday.value = "0";
      form.elements.start.value = "08:45";
      form.elements.end.value = "09:15";
      form.elements.room.value = "Phòng B12";
      form.requestSubmit(find("button", form));
      const statuses = await completed(`/api/courses/${qa.courseId}/sessions`);
      const current = await managementForm("addSession");
      const retained = ["start", "end", "room"].map(key => current.elements[key].value);
      return result(statuses.includes(409) && retained.every(value => !value), {
        "Đã nhập": "08:45–09:15 · Phòng B12",
        "Kết quả lưu": statuses.join(", "),
        "Thông báo": text("#toast"),
        "Các ô sau lỗi": retained.map(value => value || "(trống)").join(" · "),
        "Kỳ vọng": "Giữ dữ liệu để giảng viên sửa phần bị trùng.",
      });
    },

    async "QA-17"() {
      const main = find("main");
      main.style.width = "min(444px, 100%)";
      main.style.marginLeft = "0";
      const overflow = (title, container) => Math.round(Math.max(
        0, title.getBoundingClientRect().right - title.closest(container).getBoundingClientRect().right,
      ));
      await selectTab("deadlines", "#content .dl");
      const assignment = Array.from(document.querySelectorAll("#content .dl strong"))
        .find(item => item.textContent === qa.longAssignment);
      if (!assignment) throw new Error("Không thấy tiêu đề bài tập 120 ký tự.");
      const assignmentOverflow = overflow(assignment, ".dl");
      await selectTab("qa", "#content .qa-compose");
      const question = Array.from(document.querySelectorAll("#content article strong"))
        .find(item => item.textContent === qa.longQuestion);
      if (!question) throw new Error("Không thấy tiêu đề câu hỏi 150 ký tự.");
      const questionOverflow = overflow(question, "article");
      question.scrollIntoView({ block: "center", inline: "start" });
      return result(assignmentOverflow > 2 || questionOverflow > 2, {
        "Khung nội dung thử": Math.round(main.getBoundingClientRect().width) + " px",
        "Tiêu đề bài tập vượt mép dòng": assignmentOverflow + " px",
        "Tiêu đề Hỏi đáp vượt mép thẻ": questionOverflow + " px",
        "Kỳ vọng": "Cả hai tiêu đề xuống dòng trong khung.",
      });
    },
  };

  async function managementForm(name) {
    return waitFor(() => find(`form[data-submit="${name}"]`, courseCard() || document), `form ${name}`);
  }

  function createPanel() {
    const panel = document.createElement("section");
    panel.className = "card";
    panel.hidden = window.location.hash === "#quay";
    panel.style.cssText = "border:2px solid #25715a;padding:18px;overflow-wrap:anywhere";
    panel.innerHTML = '<p><a href="/__qa/">← Danh sách ca kiểm thử</a></p><h3></h3>'
      + '<p id="qa-result-status" role="status"></p><dl></dl><p></p>';
    find("h3", panel).textContent = qa.code + " · " + qa.title;
    const footer = panel.lastElementChild;
    for (const [label, href] of [
      ["Chạy lại ca", "/__qa/run/" + qa.code],
      ["Ảnh ghi nhận ban đầu", "/__qa/evidence/" + qa.code + ".jpg"],
    ]) {
      const link = document.createElement("a");
      link.textContent = label;
      link.href = href;
      link.style.marginRight = "16px";
      footer.append(link);
    }
    find("#content").before(panel);
    return panel;
  }

  document.addEventListener("DOMContentLoaded", async () => {
    const panel = createPanel();
    const status = find("#qa-result-status");
    status.textContent = "Đang chuẩn bị dữ liệu mẫu…";
    try {
      await waitFor(() => !find("#app").hidden, "phiên mẫu trong EduMate");
      if (!qa.auto) {
        const expected = { timetable: "#content .week, #content .empty-state",
                           deadlines: "#content .dl, #content .empty-state",
                           qa: "#content .qa-toolbar" };
        await selectTab(qa.tab, expected[qa.tab]);
        status.textContent = "Màn hình từ dữ liệu của lượt chạy hiện tại.";
        return;
      }
      status.textContent = "Đang chạy ca kiểm thử…";
      const output = await replay[qa.code]();
      status.textContent = output.reproduced ? "Đã tái hiện hành vi" : "Không tái hiện trên checkout này";
      const list = find("dl", panel);
      for (const [label, value] of Object.entries(output.facts)) {
        const dt = document.createElement("dt");
        const dd = document.createElement("dd");
        dt.textContent = label;
        dt.style.fontWeight = "700";
        dd.textContent = value;
        list.append(dt, dd);
      }
    } catch (error) {
      status.textContent = "Không chạy được ca kiểm thử. " + error.message;
    }
  });
})();
