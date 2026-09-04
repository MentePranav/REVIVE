/**
 * REVIVE — Landing Page Client Logic (Vanilla JS)
 * Handles navigation interactions, responsive menus, and preview mockups.
 */

document.addEventListener("DOMContentLoaded", () => {
  // 1. Mobile Menu Toggle
  const navToggle = document.getElementById("nav-toggle");
  const navLinks = document.getElementById("nav-links");

  if (navToggle && navLinks) {
    navToggle.addEventListener("click", () => {
      const isOpen = navLinks.classList.toggle("mobile-open");
      navToggle.setAttribute("aria-expanded", isOpen);
      navToggle.textContent = isOpen ? "✕" : "☰";
    });

    // Close mobile menu when clicking any link
    navLinks.querySelectorAll("a").forEach(link => {
      link.addEventListener("click", () => {
        navLinks.classList.remove("mobile-open");
        navToggle.setAttribute("aria-expanded", "false");
        navToggle.textContent = "☰";
      });
    });
  }

  // 2. Active Section Highlighting in Navigation
  const sections = document.querySelectorAll("section[id]");
  const navItems = document.querySelectorAll(".nav-link[href^='#']");

  function onScroll() {
    const scrollPos = window.scrollY + 100;

    sections.forEach(section => {
      const top = section.offsetTop;
      const height = section.offsetHeight;
      const id = section.getAttribute("id");

      if (scrollPos >= top && scrollPos < top + height) {
        navItems.forEach(item => {
          if (item.getAttribute("href") === `#${id}`) {
            item.style.color = "var(--text-primary)";
          } else {
            item.style.color = "";
          }
        });
      }
    });
  }

  window.addEventListener("scroll", onScroll, { passive: true });

  // 3. Interactive Preview Mockup Demo Tab Toggle
  const mockTabs = document.querySelectorAll(".mock-scenario-btn");
  if (mockTabs.length > 0) {
    mockTabs.forEach(btn => {
      btn.addEventListener("click", () => {
        mockTabs.forEach(b => b.classList.remove("active"));
        btn.classList.add("active");

        const scenario = btn.dataset.scenario;
        updateMockPreview(scenario);
      });
    });
  }
});

function updateMockPreview(scenario) {
  const caseIdEl = document.getElementById("mock-case-id");
  const amountEl = document.getElementById("mock-amount");
  const diagEl = document.getElementById("mock-diag");
  const confEl = document.getElementById("mock-conf");
  const recEl = document.getElementById("mock-rec");
  const authEl = document.getElementById("mock-auth");
  const outcomeEl = document.getElementById("mock-outcome");

  if (!caseIdEl) return;

  if (scenario === "insufficient_funds") {
    caseIdEl.textContent = "evt_synth_1042";
    amountEl.textContent = "₹4,500.00";
    diagEl.textContent = "INSUFFICIENT_FUNDS";
    confEl.textContent = "94.2%";
    recEl.textContent = "SCHEDULED_RETRY (Salary Window: 1st)";
    authEl.textContent = "auth_a8f92b7c41";
    outcomeEl.innerHTML = '<span class="text-green">RECOVERED (+₹4,500.00)</span>';
  } else if (scenario === "abandoned_otp") {
    caseIdEl.textContent = "evt_synth_2089";
    amountEl.textContent = "₹1,850.00";
    diagEl.textContent = "ABANDONMENT_OTP_STAGE";
    confEl.textContent = "91.8%";
    recEl.textContent = "CUSTOMER_REMINDER (WhatsApp Link)";
    authEl.textContent = "auth_c4e1903fa8";
    outcomeEl.innerHTML = '<span class="text-green">RECOVERED (+₹1,850.00)</span>';
  } else if (scenario === "high_risk") {
    caseIdEl.textContent = "evt_synth_3411";
    amountEl.textContent = "₹28,000.00";
    diagEl.textContent = "SUSPICIOUS_VELOCITY_SPIKE";
    confEl.textContent = "96.5%";
    recEl.textContent = "HUMAN_REVIEW (Risk Queue)";
    authEl.textContent = "BLOCKED (P005_FRAUD_GATE)";
    outcomeEl.innerHTML = '<span class="text-yellow">ROUTED TO RISK TEAM</span>';
  }
}
