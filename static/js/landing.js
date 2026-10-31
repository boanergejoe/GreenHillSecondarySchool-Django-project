(function () {
    "use strict";

    var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    var nav = document.getElementById("siteNav");
    var navToggle = document.getElementById("navToggle");
    var primaryNav = document.getElementById("primaryNav");
    var backToTop = document.getElementById("backToTop");
    var scrollProgress = document.getElementById("scrollProgress");
    var navLinks = Array.prototype.slice.call(document.querySelectorAll(".nav-link"));

    function closeMenu() {
        document.body.classList.remove("nav-open");
        if (navToggle) {
            navToggle.setAttribute("aria-expanded", "false");
            navToggle.setAttribute("aria-label", "Open navigation menu");
        }
    }

    if (navToggle && primaryNav) {
        navToggle.addEventListener("click", function () {
            var isOpen = document.body.classList.toggle("nav-open");
            navToggle.setAttribute("aria-expanded", String(isOpen));
            navToggle.setAttribute("aria-label", isOpen ? "Close navigation menu" : "Open navigation menu");
        });

        primaryNav.addEventListener("click", function (event) {
            if (event.target.closest("a")) {
                closeMenu();
            }
        });

        document.addEventListener("click", function (event) {
            if (!document.body.classList.contains("nav-open")) {
                return;
            }
            if (!event.target.closest("#siteNav")) {
                closeMenu();
            }
        });

        document.addEventListener("keydown", function (event) {
            if (event.key === "Escape") {
                closeMenu();
            }
        });

        window.addEventListener("resize", function () {
            if (window.innerWidth > 991) {
                closeMenu();
            }
        });
    }

    function updateScrollUI() {
        var scrollTop = window.scrollY || document.documentElement.scrollTop;
        var pageHeight = document.documentElement.scrollHeight - window.innerHeight;
        var progress = pageHeight > 0 ? (scrollTop / pageHeight) * 100 : 0;

        if (nav) {
            nav.classList.toggle("scrolled", scrollTop > 34);
        }

        if (scrollProgress) {
            scrollProgress.style.width = progress + "%";
        }

        if (backToTop) {
            backToTop.classList.toggle("show", scrollTop > 650);
        }
    }

    var scrollTicking = false;
    window.addEventListener("scroll", function () {
        if (!scrollTicking) {
            window.requestAnimationFrame(function () {
                updateScrollUI();
                scrollTicking = false;
            });
            scrollTicking = true;
        }
    }, { passive: true });

    updateScrollUI();

    if (backToTop) {
        backToTop.addEventListener("click", function () {
            window.scrollTo({ top: 0, behavior: reduceMotion ? "auto" : "smooth" });
        });
    }

    var sectionLinks = navLinks.map(function (link) {
        var hash = link.hash;
        if (!hash || hash === "#") {
            return null;
        }
        return {
            link: link,
            section: document.getElementById(hash.slice(1))
        };
    }).filter(function (entry) {
        return entry && entry.section;
    });

    if ("IntersectionObserver" in window && sectionLinks.length) {
        var sectionObserver = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (!entry.isIntersecting) {
                    return;
                }
                var activeLink = null;
                sectionLinks.forEach(function (item) {
                    if (item.section === entry.target) {
                        activeLink = item.link;
                    }
                });
                if (!activeLink) {
                    return;
                }
                navLinks.forEach(function (link) {
                    var isActive = link === activeLink;
                    link.classList.toggle("active", isActive);
                    if (isActive) {
                        link.setAttribute("aria-current", "page");
                    } else {
                        link.removeAttribute("aria-current");
                    }
                });
            });
        }, {
            rootMargin: "-41% 0px -52% 0px",
            threshold: 0
        });

        sectionLinks.forEach(function (item) {
            sectionObserver.observe(item.section);
        });
    }

    document.querySelectorAll("[data-dialog-open]").forEach(function (button) {
        button.addEventListener("click", function () {
            var dialog = document.getElementById(button.getAttribute("data-dialog-open"));
            if (dialog && typeof dialog.showModal === "function") {
                dialog.showModal();
            }
        });
    });

    document.querySelectorAll("[data-dialog-close]").forEach(function (button) {
        button.addEventListener("click", function () {
            var dialog = button.closest("dialog");
            if (dialog) {
                dialog.close();
            }
        });
    });

    document.querySelectorAll(".legal-dialog").forEach(function (dialog) {
        dialog.addEventListener("click", function (event) {
            if (event.target === dialog) {
                dialog.close();
            }
        });
    });

    var galleryDialog = document.getElementById("galleryDialog");
    var galleryImage = galleryDialog ? galleryDialog.querySelector("[data-gallery-image]") : null;
    var galleryKicker = galleryDialog ? galleryDialog.querySelector("[data-gallery-kicker]") : null;
    var galleryTitle = galleryDialog ? galleryDialog.querySelector("[data-gallery-title]") : null;

    document.querySelectorAll("[data-gallery-open]").forEach(function (link) {
        link.addEventListener("click", function (event) {
            if (!galleryDialog || !galleryImage || typeof galleryDialog.showModal !== "function") {
                return;
            }

            event.preventDefault();
            galleryImage.src = link.getAttribute("data-full");
            galleryImage.alt = link.getAttribute("data-alt") || "";
            galleryKicker.textContent = link.getAttribute("data-kicker") || "";
            galleryTitle.textContent = link.getAttribute("data-title") || "";
            galleryDialog.showModal();
        });
    });

    if (galleryDialog) {
        galleryDialog.addEventListener("click", function (event) {
            if (event.target === galleryDialog) {
                galleryDialog.close();
            }
        });

        galleryDialog.querySelectorAll("[data-gallery-close]").forEach(function (button) {
            button.addEventListener("click", function () {
                galleryDialog.close();
            });
        });
    }

    var counters = Array.prototype.slice.call(document.querySelectorAll("[data-counter]"));
    var countersStarted = false;

    function formatCounter(value, decimals) {
        return new Intl.NumberFormat("en-US", {
            minimumFractionDigits: decimals,
            maximumFractionDigits: decimals
        }).format(value);
    }

    function runCounters() {
        if (countersStarted) {
            return;
        }
        countersStarted = true;

        counters.forEach(function (counter) {
            var target = parseFloat(counter.getAttribute("data-counter")) || 0;
            var decimals = parseInt(counter.getAttribute("data-decimals") || "0", 10);
            var suffix = counter.getAttribute("data-suffix") || "";
            var duration = 1500;
            var startTime = null;

            if (reduceMotion) {
                counter.textContent = formatCounter(target, decimals) + suffix;
                return;
            }

            counter.textContent = formatCounter(0, decimals) + suffix;

            function step(timestamp) {
                if (!startTime) {
                    startTime = timestamp;
                }
                var elapsed = timestamp - startTime;
                var progress = Math.min(elapsed / duration, 1);
                var eased = 1 - Math.pow(1 - progress, 3);
                counter.textContent = formatCounter(target * eased, decimals) + suffix;
                if (progress < 1) {
                    window.requestAnimationFrame(step);
                }
            }

            window.requestAnimationFrame(step);
        });
    }

    var metricsSection = document.querySelector(".metrics");
    if (counters.length) {
        if (metricsSection && "IntersectionObserver" in window) {
            var counterObserver = new IntersectionObserver(function (entries) {
                if (entries.some(function (entry) { return entry.isIntersecting; })) {
                    runCounters();
                    counterObserver.disconnect();
                }
            }, { threshold: 0.25 });
            counterObserver.observe(metricsSection);
        } else {
            runCounters();
        }
    }

    var slides = Array.prototype.slice.call(document.querySelectorAll(".testimonial-slide"));
    var dots = Array.prototype.slice.call(document.querySelectorAll(".slider-dot"));
    var prevButton = document.getElementById("testimonialPrev");
    var nextButton = document.getElementById("testimonialNext");
    var sliderShell = document.querySelector(".testimonial-shell");
    var currentSlide = 0;
    var autoplayTimer = null;
    var sliderPaused = false;

    function showSlide(index) {
        if (!slides.length) {
            return;
        }

        currentSlide = (index + slides.length) % slides.length;

        slides.forEach(function (slide, slideIndex) {
            var isActive = slideIndex === currentSlide;
            slide.classList.toggle("active", isActive);
            slide.setAttribute("aria-hidden", String(!isActive));
        });

        dots.forEach(function (dot, dotIndex) {
            var isActive = dotIndex === currentSlide;
            dot.classList.toggle("active", isActive);
            dot.setAttribute("aria-pressed", String(isActive));
        });
    }

    function startAutoplay() {
        if (reduceMotion || slides.length < 2 || sliderPaused) {
            return;
        }
        window.clearInterval(autoplayTimer);
        autoplayTimer = window.setInterval(function () {
            showSlide(currentSlide + 1);
        }, 6500);
    }

    function stopAutoplay() {
        window.clearInterval(autoplayTimer);
        autoplayTimer = null;
    }

    if (slides.length) {
        showSlide(0);
        startAutoplay();

        if (prevButton) {
            prevButton.addEventListener("click", function () {
                showSlide(currentSlide - 1);
                startAutoplay();
            });
        }

        if (nextButton) {
            nextButton.addEventListener("click", function () {
                showSlide(currentSlide + 1);
                startAutoplay();
            });
        }

        dots.forEach(function (dot) {
            dot.addEventListener("click", function () {
                showSlide(parseInt(dot.getAttribute("data-slide-to"), 10));
                startAutoplay();
            });
        });

        if (sliderShell) {
            sliderShell.addEventListener("pointerenter", function () {
                sliderPaused = true;
                stopAutoplay();
            });

            sliderShell.addEventListener("pointerleave", function () {
                sliderPaused = false;
                startAutoplay();
            });

            sliderShell.addEventListener("focusin", function () {
                sliderPaused = true;
                stopAutoplay();
            });

            sliderShell.addEventListener("focusout", function (event) {
                if (!sliderShell.contains(event.relatedTarget)) {
                    sliderPaused = false;
                    startAutoplay();
                }
            });

            sliderShell.addEventListener("keydown", function (event) {
                if (event.key === "ArrowLeft") {
                    showSlide(currentSlide - 1);
                    startAutoplay();
                }
                if (event.key === "ArrowRight") {
                    showSlide(currentSlide + 1);
                    startAutoplay();
                }
            });
        }
    }

    var aosReady = typeof window.AOS !== "undefined";
    if (aosReady) {
        window.AOS.init({
            duration: 720,
            easing: "ease-out-cubic",
            once: true,
            offset: 80,
            disable: reduceMotion
        });
    } else {
        document.querySelectorAll("[data-aos]").forEach(function (element) {
            element.removeAttribute("data-aos");
            element.style.opacity = "1";
            element.style.transform = "none";
        });
    }

    if (window.gsap && !reduceMotion) {
        var heroTimeline = window.gsap.timeline({
            defaults: { ease: "power3.out", duration: 0.85 }
        });
        var heroEyebrow = document.querySelector(".hero .eyebrow");
        var heroTitle = document.querySelector(".hero-title");
        var heroLead = document.querySelector(".hero-lead");
        var heroActions = document.querySelector(".hero-actions");
        var heroVisual = document.querySelector(".school-welcome-card, .dashboard-device");

        if (heroEyebrow) {
            heroTimeline.from(heroEyebrow, { y: 18, opacity: 0, duration: 0.55 });
        }
        if (heroTitle) {
            heroTimeline.from(heroTitle, { y: 28, opacity: 0 }, "-=0.28");
        }
        if (heroLead) {
            heroTimeline.from(heroLead, { y: 22, opacity: 0 }, "-=0.55");
        }
        if (heroActions) {
            heroTimeline.from(heroActions, { y: 18, opacity: 0 }, "-=0.58");
        }
        if (heroVisual) {
            heroTimeline.from(
                heroVisual,
                { y: 34, opacity: 0, duration: 0.9, clearProps: "transform,opacity" },
                "-=0.55"
            );
        }
    }
})();
