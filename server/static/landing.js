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

  // 2. Active Section Highlighting & Subtle State in Navigation
  const navbar = document.querySelector(".navbar");
  const sections = document.querySelectorAll("section[id]");
  const navItems = document.querySelectorAll(".nav-link[href^='#']");

  function onScroll() {
    const scrollY = window.scrollY;
    if (navbar) {
      if (scrollY > 20) {
        navbar.classList.add("navbar-scrolled");
      } else {
        navbar.classList.remove("navbar-scrolled");
      }
    }

    const scrollPos = scrollY + 120;

    sections.forEach(section => {
      const top = section.offsetTop;
      const height = section.offsetHeight;
      const id = section.getAttribute("id");

      if (scrollPos >= top && scrollPos < top + height) {
        navItems.forEach(item => {
          if (item.getAttribute("href") === `#${id}`) {
            item.classList.add("active");
          } else {
            item.classList.remove("active");
          }
        });
      }
    });
  }

  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll(); // initial state check

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

  // 4. Ambient Kinetic Background
  initKineticBackground();

  // 5. Scroll Reveal Motion System (Phase N7)
  initScrollReveals();
});

/**
 * Phase N7: Single IntersectionObserver for scroll-triggered section reveals.
 * Safe progressive enhancement: content remains 100% visible if JS is disabled.
 */
function initScrollReveals() {
  const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (prefersReducedMotion) return;

  if (!("IntersectionObserver" in window)) return;

  // Add readiness class to root to enable reveal transitions safely
  document.documentElement.classList.add("js-reveal-ready");

  const revealObserver = new IntersectionObserver((entries, observer) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add("is-revealed");
        observer.unobserve(entry.target);
      }
    });
  }, {
    root: null,
    rootMargin: "0px 0px -40px 0px",
    threshold: 0.08
  });

  const revealElements = document.querySelectorAll(".reveal-on-scroll");
  revealElements.forEach(el => revealObserver.observe(el));
}

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

/**
 * Ambient Kinetic Particle & Network Field Engine
 * Lightweight, high-performance HTML5 Canvas animation designed for fintech/AI infrastructure aesthetic.
 */
function initKineticBackground() {
  const canvas = document.getElementById("bg-canvas");
  if (!canvas) return;

  const ctx = canvas.getContext("2d", { alpha: true });
  if (!ctx) return;

  let width = 0;
  let height = 0;
  let dpr = 1;
  let animId = null;
  const particles = [];

  // Burst / Firework state (Phase N4)
  const burstParticles = [];
  const burstRings = [];
  const MAX_BURST_PARTICLES = 100;
  const MAX_BURST_RINGS = 4;

  // Cursor tracking state (Phase N3)
  const cursor = {
    x: -1000,
    y: -1000,
    targetX: -1000,
    targetY: -1000,
    radius: 140,
    glowRadius: 180,
    active: false,
    opacity: 0,
  };

  // Coarse pointer / touch detection
  const isCoarse = window.matchMedia("(pointer: coarse)");

  // Reduced motion preference check
  const motionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
  let prefersReducedMotion = motionQuery.matches;

  if (motionQuery.addEventListener) {
    motionQuery.addEventListener("change", (e) => {
      prefersReducedMotion = e.matches;
      if (prefersReducedMotion) {
        burstParticles.length = 0;
        burstRings.length = 0;
        stopAnimation();
        renderStaticField();
      } else if (!document.hidden) {
        startAnimation();
      }
    });
  }

  // Phase N2: Ambient Particle
  class Particle {
    constructor(w, h) {
      this.reset(w, h, true);
    }

    reset(w, h, randomInit = false) {
      this.x = randomInit ? Math.random() * w : (Math.random() > 0.5 ? 0 : w);
      this.y = randomInit ? Math.random() * h : Math.random() * h;

      // Slow, subtle, organic drift (0.15 - 0.40 px/frame)
      const speed = 0.15 + Math.random() * 0.25;
      const angle = Math.random() * Math.PI * 2;
      this.vx = Math.cos(angle) * speed;
      this.vy = Math.sin(angle) * speed;

      // Depth variation: radius (0.8px - 1.9px) and alpha (0.20 - 0.55)
      this.radius = 0.8 + Math.random() * 1.1;
      this.baseAlpha = 0.20 + Math.random() * 0.35;
      // Soft fintech palette (accent blue / cyan / subtle slate)
      this.isCyan = Math.random() > 0.72;
    }

    update(w, h, cur) {
      this.x += this.vx;
      this.y += this.vy;

      // Phase N3: Subtle cursor repulsion (smooth non-jarring nudge)
      if (cur && cur.opacity > 0.01 && cur.x > -500) {
        const dx = this.x - cur.x;
        const dy = this.y - cur.y;
        const distSq = dx * dx + dy * dy;
        const cursorRadiusSq = cur.radius * cur.radius;

        if (distSq < cursorRadiusSq && distSq > 0.01) {
          const dist = Math.sqrt(distSq);
          const norm = 1 - dist / cur.radius;
          const force = norm * 0.75 * cur.opacity;
          const angle = Math.atan2(dy, dx);
          this.x += Math.cos(angle) * force;
          this.y += Math.sin(angle) * force;
        }
      }

      // Smooth wrap around screen edges
      if (this.x < -10) this.x = w + 10;
      else if (this.x > w + 10) this.x = -10;

      if (this.y < -10) this.y = h + 10;
      else if (this.y > h + 10) this.y = -10;
    }

    draw(context) {
      context.beginPath();
      context.arc(this.x, this.y, this.radius, 0, Math.PI * 2);
      if (this.isCyan) {
        context.fillStyle = `rgba(56, 189, 248, ${this.baseAlpha})`;
      } else {
        context.fillStyle = `rgba(96, 165, 250, ${this.baseAlpha})`;
      }
      context.fill();
    }
  }

  // Phase N4: Digital Energy Burst Particle
  class BurstParticle {
    constructor(x, y, isTouch) {
      this.x = x;
      this.y = y;
      const angle = Math.random() * Math.PI * 2;
      const speed = isTouch ? (0.8 + Math.random() * 1.6) : (1.2 + Math.random() * 2.2);
      this.vx = Math.cos(angle) * speed;
      this.vy = Math.sin(angle) * speed;
      this.friction = 0.94;
      this.size = 0.8 + Math.random() * (isTouch ? 0.7 : 1.1);
      this.maxLife = isTouch ? Math.floor(24 + Math.random() * 14) : Math.floor(34 + Math.random() * 20);
      this.life = this.maxLife;

      const roll = Math.random();
      if (roll > 0.82) {
        this.rgb = "224, 242, 254"; // crisp white-blue highlight
      } else if (roll > 0.35) {
        this.rgb = "56, 189, 248";  // cyan
      } else {
        this.rgb = "96, 165, 250";  // blue
      }
    }

    update() {
      this.vx *= this.friction;
      this.vy *= this.friction;
      this.x += this.vx;
      this.y += this.vy;
      this.life--;
    }

    draw(context) {
      const progress = this.life / this.maxLife;
      const alpha = progress * 0.75;
      context.beginPath();
      context.arc(this.x, this.y, this.size * progress, 0, Math.PI * 2);
      context.fillStyle = `rgba(${this.rgb}, ${alpha})`;
      context.fill();
    }
  }

  // Phase N4: Expanding Energy Ring
  class BurstRing {
    constructor(x, y, isTouch) {
      this.x = x;
      this.y = y;
      this.radius = 2;
      this.maxRadius = isTouch ? 40 : 65;
      this.growthSpeed = isTouch ? 1.5 : 2.2;
      this.maxLife = isTouch ? 24 : 32;
      this.life = this.maxLife;
      this.isCyan = Math.random() > 0.4;
    }

    update() {
      this.radius += (this.maxRadius - this.radius) * 0.12 + this.growthSpeed * 0.4;
      this.life--;
    }

    draw(context) {
      const progress = this.life / this.maxLife;
      const alpha = progress * 0.30;
      context.beginPath();
      context.arc(this.x, this.y, this.radius, 0, Math.PI * 2);
      context.strokeStyle = this.isCyan
        ? `rgba(56, 189, 248, ${alpha})`
        : `rgba(96, 165, 250, ${alpha})`;
      context.lineWidth = 1.0 * progress;
      context.stroke();
    }
  }

  function createEnergyBurst(x, y, isTouch) {
    if (prefersReducedMotion) return;

    // Hard limit on active rings
    if (burstRings.length >= MAX_BURST_RINGS) {
      burstRings.shift();
    }
    burstRings.push(new BurstRing(x, y, isTouch));

    const count = isTouch ? 10 : 16;
    const available = MAX_BURST_PARTICLES - burstParticles.length;
    if (available < count) {
      burstParticles.splice(0, count - available);
    }

    for (let i = 0; i < count; i++) {
      burstParticles.push(new BurstParticle(x, y, isTouch));
    }
  }

  function getTargetParticleCount(w) {
    if (w >= 1200) return 80;
    if (w >= 768) return 50;
    return 28;
  }

  function recalculateParticles() {
    const targetCount = getTargetParticleCount(width);

    // Adjust particle array size
    while (particles.length < targetCount) {
      particles.push(new Particle(width, height));
    }
    if (particles.length > targetCount) {
      particles.length = targetCount;
    }

    // Keep particles within viewport bounds
    for (let i = 0; i < particles.length; i++) {
      if (particles[i].x > width) particles[i].x = Math.random() * width;
      if (particles[i].y > height) particles[i].y = Math.random() * height;
    }
  }

  function resizeCanvas() {
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    width = window.innerWidth;
    height = window.innerHeight;

    canvas.width = Math.floor(width * dpr);
    canvas.height = Math.floor(height * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    recalculateParticles();
  }

  function renderConnections() {
    const maxDist = width < 768 ? 85 : 120;
    const maxDistSq = maxDist * maxDist;
    const len = particles.length;

    for (let i = 0; i < len; i++) {
      const p1 = particles[i];
      for (let j = i + 1; j < len; j++) {
        const p2 = particles[j];
        const dx = p1.x - p2.x;
        const dy = p1.y - p2.y;
        const distSq = dx * dx + dy * dy;

        if (distSq < maxDistSq) {
          const dist = Math.sqrt(distSq);
          const norm = 1 - dist / maxDist;
          // Extremely subtle alpha (max 0.10) to preserve text readability
          const lineAlpha = norm * 0.10;
          ctx.beginPath();
          ctx.moveTo(p1.x, p1.y);
          ctx.lineTo(p2.x, p2.y);
          ctx.strokeStyle = `rgba(96, 165, 250, ${lineAlpha})`;
          ctx.lineWidth = 0.65;
          ctx.stroke();
        }
      }
    }
  }

  function renderFrame() {
    ctx.clearRect(0, 0, width, height);

    // 1. Smoothly interpolate cursor coordinates and opacity
    if (cursor.active) {
      if (cursor.x < -500) {
        cursor.x = cursor.targetX;
        cursor.y = cursor.targetY;
      } else {
        cursor.x += (cursor.targetX - cursor.x) * 0.18;
        cursor.y += (cursor.targetY - cursor.y) * 0.18;
      }
      cursor.opacity += (1 - cursor.opacity) * 0.10;
    } else {
      cursor.opacity += (0 - cursor.opacity) * 0.08;
      if (cursor.opacity < 0.005) {
        cursor.opacity = 0;
        cursor.x = -1000;
        cursor.y = -1000;
      }
    }

    // 2. Draw subtle ambient cursor glow behind connections & particles
    if (cursor.opacity > 0.01 && cursor.x > -500) {
      const glow = ctx.createRadialGradient(cursor.x, cursor.y, 0, cursor.x, cursor.y, cursor.glowRadius);
      glow.addColorStop(0, `rgba(59, 130, 246, ${0.06 * cursor.opacity})`);
      glow.addColorStop(0.5, `rgba(6, 182, 212, ${0.02 * cursor.opacity})`);
      glow.addColorStop(1, "rgba(7, 10, 17, 0)");
      ctx.fillStyle = glow;
      ctx.beginPath();
      ctx.arc(cursor.x, cursor.y, cursor.glowRadius, 0, Math.PI * 2);
      ctx.fill();
    }

    // 3. Draw energy burst rings (Phase N4)
    for (let i = burstRings.length - 1; i >= 0; i--) {
      const ring = burstRings[i];
      ring.update();
      ring.draw(ctx);
      if (ring.life <= 0) {
        burstRings.splice(i, 1);
      }
    }

    // 4. Draw energy burst particles (Phase N4)
    for (let i = burstParticles.length - 1; i >= 0; i--) {
      const bp = burstParticles[i];
      bp.update();
      bp.draw(ctx);
      if (bp.life <= 0) {
        burstParticles.splice(i, 1);
      }
    }

    // 5. Draw network connections (Phase N2)
    renderConnections();

    // 6. Update and draw ambient particles with cursor influence (Phase N2 + N3)
    const len = particles.length;
    for (let i = 0; i < len; i++) {
      particles[i].update(width, height, cursor);
      particles[i].draw(ctx);
    }

    animId = requestAnimationFrame(renderFrame);
  }

  function startAnimation() {
    if (animId !== null || prefersReducedMotion || document.hidden) return;
    animId = requestAnimationFrame(renderFrame);
  }

  function stopAnimation() {
    if (animId !== null) {
      cancelAnimationFrame(animId);
      animId = null;
    }
  }

  function renderStaticField() {
    ctx.clearRect(0, 0, width, height);
    burstParticles.length = 0;
    burstRings.length = 0;
    const len = Math.min(particles.length, 30);
    for (let i = 0; i < len; i++) {
      particles[i].draw(ctx);
    }
  }

  // Pointer Interaction Listeners (Desktop only)
  function handlePointerMove(e) {
    if (prefersReducedMotion || isCoarse.matches || e.pointerType === "touch") {
      cursor.active = false;
      return;
    }
    cursor.targetX = e.clientX;
    cursor.targetY = e.clientY;
    cursor.active = true;
  }

  function handlePointerLeave() {
    cursor.active = false;
  }

  // Phase N4: Pointer / Tap Energy Burst Trigger
  function handlePointerDown(e) {
    if (prefersReducedMotion) return;

    // Primary button or touch tap only
    if (e.button !== undefined && e.button !== 0) return;

    // Interactive element safeguards: do not burst on buttons, links, inputs, tabs
    const target = e.target;
    if (target && target.closest) {
      const isInteractive = target.closest(
        "a, button, input, select, textarea, summary, [role='button'], [role='link'], [role='tab'], .btn, .nav-toggle, .mock-scenario-btn, .header-home-link"
      );
      if (isInteractive) return;
    }

    const isTouch = e.pointerType === "touch" || isCoarse.matches;
    createEnergyBurst(e.clientX, e.clientY, isTouch);
  }

  window.addEventListener("pointermove", handlePointerMove, { passive: true });
  window.addEventListener("pointerleave", handlePointerLeave, { passive: true });
  window.addEventListener("blur", handlePointerLeave, { passive: true });
  window.addEventListener("pointerdown", handlePointerDown, { passive: true });

  // Lifecycle & Performance Listeners
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) {
      stopAnimation();
    } else if (!prefersReducedMotion) {
      startAnimation();
    }
  });

  let resizeTimer = null;
  window.addEventListener("resize", () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => {
      resizeCanvas();
      if (prefersReducedMotion) {
        renderStaticField();
      }
    }, 120);
  }, { passive: true });

  // Initial setup
  resizeCanvas();

  if (prefersReducedMotion) {
    renderStaticField();
  } else {
    startAnimation();
  }
}
