import { Shield, Users, TrendingUp, Heart, Lock, BarChart3, Check, Menu, X } from 'lucide-react';
import { KioLogo } from './KioLogo';
import { KioMascot } from './KioMascot';
import { Reveal } from './landing/Reveal';
import { TheRealitySection } from './landing/TheRealitySection';
import { TheShiftSection } from './landing/TheShiftSection';
import { WhyKioSection } from './landing/WhyKioSection';
import { ProductStorySection } from './landing/ProductStorySection';
import { SectionLabel } from './landing/SectionLabel';
import { AnchorLink, TransitionLink } from './landing/TransitionLink';
import { useState } from 'react';

export function LandingPage() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  return (
    <div className="min-h-screen bg-white">
      {/* Header */}
      <header className="sticky top-0 z-50 bg-white/95 backdrop-blur-sm border-b border-border">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center gap-2">
              <KioLogo className="h-8 w-auto" />
            </div>

            <nav className="hidden md:flex items-center gap-7">
              <AnchorLink href="#why-kio" className="text-muted-foreground hover:text-foreground transition">Why Kio</AnchorLink>
              <AnchorLink href="#how-it-works" className="text-muted-foreground hover:text-foreground transition">How It Works</AnchorLink>
              <AnchorLink href="#features" className="text-muted-foreground hover:text-foreground transition">Features</AnchorLink>
              <AnchorLink href="#pricing" className="text-muted-foreground hover:text-foreground transition">Pricing</AnchorLink>
              <TransitionLink to="/login" className="text-muted-foreground hover:text-foreground transition">Sign In</TransitionLink>
              <TransitionLink to="/login" className="px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition motion-safe:active:scale-[0.97]">
                Start Free
              </TransitionLink>
            </nav>

            <button
              className="md:hidden"
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            >
              {mobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
            </button>
          </div>
        </div>

        {/* Mobile menu */}
        {mobileMenuOpen && (
          <div className="md:hidden border-t border-border bg-white">
            <nav className="flex flex-col px-4 py-4 gap-4">
              <AnchorLink href="#why-kio" onClick={() => setMobileMenuOpen(false)} className="text-muted-foreground hover:text-foreground transition">Why Kio</AnchorLink>
              <AnchorLink href="#how-it-works" onClick={() => setMobileMenuOpen(false)} className="text-muted-foreground hover:text-foreground transition">How It Works</AnchorLink>
              <AnchorLink href="#features" onClick={() => setMobileMenuOpen(false)} className="text-muted-foreground hover:text-foreground transition">Features</AnchorLink>
              <AnchorLink href="#pricing" onClick={() => setMobileMenuOpen(false)} className="text-muted-foreground hover:text-foreground transition">Pricing</AnchorLink>
              <TransitionLink to="/login" className="text-muted-foreground hover:text-foreground transition">Sign In</TransitionLink>
              <TransitionLink to="/login" className="px-4 py-2 bg-primary text-primary-foreground rounded-lg text-center transition motion-safe:active:scale-[0.97]">
                Start Free
              </TransitionLink>
            </nav>
          </div>
        )}
      </header>

      {/* Hero Section */}
      <section className="relative overflow-hidden bg-gradient-to-br from-indigo-50 via-white to-teal-50 py-14 md:py-16 lg:py-20">
        {/* Soft Kio atmosphere behind the hero. Decorative only. */}
        <div aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden">
          <div className="absolute -left-24 -top-16 h-80 w-80 rounded-full bg-violet-200/40 blur-3xl animate-kio-drift" />
          <div className="absolute right-0 top-1/3 h-96 w-96 translate-x-1/3 rounded-full bg-teal-200/35 blur-3xl" />
        </div>

        <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid md:grid-cols-2 gap-10 items-center lg:gap-12">
            <Reveal from="left">
              <SectionLabel align="left">For students, parents, counselors and schools</SectionLabel>
              <h1 className="mt-6 mb-5 text-[2.75rem] font-bold leading-[1.1] text-foreground sm:text-5xl lg:text-[4rem]">
                A space where every student{' '}
                <span className="text-secondary">feels heard</span>.
              </h1>
              <p className="mb-8 max-w-xl text-xl leading-relaxed text-muted-foreground md:text-[1.375rem]">
                Kio is a private AI companion for students — and a gentle way for the people around
                them to offer support earlier. Insights are shared. Conversations are not.
              </p>
              <div className="flex flex-col sm:flex-row gap-4">
                <TransitionLink to="/login" className="px-8 py-4 bg-primary text-primary-foreground rounded-xl text-[1.0625rem] font-medium hover:bg-primary/90 shadow-lg text-center transition motion-safe:active:scale-[0.97]">
                  Start Free
                </TransitionLink>
                <AnchorLink href="#reality" className="px-8 py-4 bg-white text-primary border-2 border-primary rounded-xl text-[1.0625rem] font-medium hover:bg-blue-50 text-center transition motion-safe:active:scale-[0.97]">
                  See why Kio exists
                </AnchorLink>
              </div>
            </Reveal>

            <Reveal from="right" delay={120} className="relative">
              <div
                aria-hidden
                className="pointer-events-none absolute -inset-4 rounded-[2.5rem] bg-gradient-to-br from-violet-200/50 to-teal-100/50 blur-2xl"
              />
              <div className="relative bg-white rounded-3xl shadow-[0_28px_70px_-28px_rgba(35,43,109,0.5)] p-6 sm:p-8 border border-white">
                <div className="flex items-center gap-3 mb-6">
                  <KioMascot size={48} />
                  <div>
                    <div className="text-lg font-medium text-foreground">Comrade</div>
                    <div className="text-sm text-muted-foreground">Your space, whenever you need it</div>
                  </div>
                </div>
                <div className="space-y-4">
                  <div className="ml-auto max-w-[85%] rounded-[1.25rem_1.25rem_0.375rem_1.25rem] bg-gradient-to-br from-indigo-50 to-indigo-100 p-4">
                    <p className="text-[0.9375rem] text-foreground">I have exams next week and I can&apos;t focus.</p>
                  </div>
                  <div className="max-w-[90%] rounded-[1.25rem_1.25rem_1.25rem_0.375rem] bg-gradient-to-br from-teal-50 to-emerald-50 p-4">
                    <p className="text-[0.9375rem] text-foreground">
                      That sounds exhausting. Let&apos;s start with just tonight — what&apos;s the one
                      thing weighing on you most?
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <div className="px-4 py-2 bg-muted rounded-full text-sm">Study tips</div>
                    <div className="px-4 py-2 bg-muted rounded-full text-sm">Confidence</div>
                    <div className="px-4 py-2 bg-muted rounded-full text-sm">Talk to someone</div>
                  </div>
                </div>
              </div>
            </Reveal>
          </div>
        </div>
      </section>

      <TheRealitySection />
      <TheShiftSection />
      <WhyKioSection />
      <ProductStorySection />

      {/* Features */}
      <section id="features" className="scroll-mt-20 py-16 md:py-20 bg-gradient-to-br from-[#F7F6FE] to-[#EEF3FE]">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <Reveal className="text-center mb-12">
            <SectionLabel>What&apos;s inside</SectionLabel>
            <h2 className="mt-5 mb-4 text-[2.25rem] font-bold leading-[1.15] text-foreground sm:text-4xl md:text-5xl">
              Built around trust
            </h2>
            <p className="mx-auto max-w-2xl text-xl leading-relaxed text-muted-foreground">
              Every part of Kio is designed so a student can be honest — and so the adults around
              them can still help.
            </p>
          </Reveal>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            {[
              {
                icon: Shield,
                title: "Student Privacy Promise",
                description: "End-to-end encryption. Parents never see raw conversations. Students feel safe to share.",
                color: "from-blue-500 to-blue-600"
              },
              {
                icon: Heart,
                title: "AI Wellness Companion",
                description: "24/7 emotional support, stress management, and personalized guidance for students.",
                color: "from-emerald-500 to-emerald-600"
              },
              {
                icon: TrendingUp,
                title: "Parent Insights",
                description: "Wellness trends, risk alerts, and actionable parenting recommendations.",
                color: "from-purple-500 to-purple-600"
              },
              {
                icon: Users,
                title: "Human Counselor Escalation",
                description: "Professional counselors receive AI-generated summaries for efficient intervention.",
                color: "from-pink-500 to-pink-600"
              },
              {
                icon: BarChart3,
                title: "School Analytics",
                description: "Anonymous aggregated data helps schools understand and improve student wellness.",
                color: "from-amber-500 to-amber-600"
              },
              {
                icon: Lock,
                title: "HIPAA Compliant",
                description: "Enterprise-grade security and compliance for educational institutions.",
                color: "from-indigo-500 to-indigo-600"
              }
            ].map((feature, index) => (
              <Reveal key={index} delay={(index % 3) * 80} className="bg-white rounded-2xl p-7 shadow-lg border border-border hover:shadow-xl hover:-translate-y-1 transition duration-300">
                <div className={`w-12 h-12 bg-gradient-to-br ${feature.color} rounded-xl flex items-center justify-center mb-4`}>
                  <feature.icon className="w-6 h-6 text-white" />
                </div>
                <h3 className="mb-3 text-xl font-semibold text-foreground">{feature.title}</h3>
                <p className="text-[1.0625rem] leading-relaxed text-muted-foreground">{feature.description}</p>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* Student Privacy Promise */}
      <section className="py-14 md:py-16 bg-white">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
          <Reveal className="relative overflow-hidden bg-gradient-to-br from-[#232B6D] via-[#3A45A8] to-[#5A6BFF] rounded-3xl p-8 sm:p-10 text-white shadow-[0_28px_70px_-28px_rgba(35,43,109,0.65)]">
            <div aria-hidden className="pointer-events-none absolute -right-20 -top-20 h-64 w-64 rounded-full bg-[#31D7C2]/25 blur-3xl" />
            <div className="relative flex items-center gap-3 mb-6">
              <Lock className="w-9 h-9 shrink-0" aria-hidden />
              <h2 className="text-2xl font-bold sm:text-3xl">Our privacy promise</h2>
            </div>
            <p className="relative mb-7 text-xl leading-relaxed text-blue-100">
              We believe trust is the foundation of effective mental health support. That's why we built Kio with privacy at its core.
            </p>
            <div className="relative grid md:grid-cols-2 gap-4 sm:gap-5">
              {[
                "Parents never see raw student conversations",
                "End-to-end encryption for all communications",
                "Students control what information is shared",
                "FERPA and COPPA compliant",
                "Optional anonymous mode for sensitive topics",
                "Data deletion upon request"
              ].map((promise, index) => (
                <div key={index} className="flex items-start gap-3">
                  <Check className="w-6 h-6 flex-shrink-0 text-emerald-300" />
                  <span className="text-[1.0625rem] text-blue-50">{promise}</span>
                </div>
              ))}
            </div>
          </Reveal>
        </div>
      </section>

      {/* Pricing */}
      <section id="pricing" className="scroll-mt-20 py-16 md:py-20 bg-gradient-to-br from-[#F7F6FE] to-[#EAF9F7]">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <Reveal className="text-center mb-12">
            <SectionLabel>Pricing</SectionLabel>
            <h2 className="mt-5 mb-4 text-[2.25rem] font-bold leading-[1.15] text-foreground sm:text-4xl md:text-5xl">
              Start where you are
            </h2>
            <p className="mx-auto max-w-2xl text-xl leading-relaxed text-muted-foreground">Choose the plan that fits your family or your school.</p>
          </Reveal>

          <div className="grid md:grid-cols-3 gap-6 max-w-6xl mx-auto">
            {[
              {
                name: "Individual",
                price: "INR 199",
                period: "per student/month",
                description: "Perfect for families",
                features: [
                  "AI wellness companion",
                  "Parent insights dashboard",
                  "Mood tracking & journaling",
                  "24/7 support",
                  "Mobile app access"
                ],
                cta: "Start Free Trial",
                featured: false
              },
              {
                name: "School",
                price: "custom",
                period: "per student/month",
                description: "For educational institutions",
                features: [
                  "Everything in Individual",
                  "School analytics dashboard",
                  "Counselor portal access",
                  "Bulk student management",
                  "Custom integrations",
                  "Dedicated support"
                ],
                cta: "Book Demo",
                featured: true
              },
              {
                name: "Enterprise",
                price: "Custom",
                period: "pricing",
                description: "For large organizations",
                features: [
                  "Everything in School",
                  "Advanced analytics",
                  "Custom AI training/ Workshops"
                  
                ],
                cta: "Contact Sales",
                featured: false
              }
            ].map((plan, index) => (
              <div
                key={index}
                className={`bg-white rounded-2xl p-7 shadow-lg border-2 ${
                  plan.featured ? 'border-primary scale-105' : 'border-border'
                } hover:shadow-xl transition`}
              >
                {plan.featured && (
                  <div className="bg-primary text-primary-foreground text-sm font-medium px-3 py-1 rounded-full inline-block mb-4">
                    Most Popular
                  </div>
                )}
                <h3 className="mb-2 text-2xl font-bold text-foreground">{plan.name}</h3>
                <div className="mb-4">
                  <span className="text-4xl font-bold text-foreground">{plan.price}</span>
                  <span className="text-muted-foreground ml-2">{plan.period}</span>
                </div>
                <p className="text-muted-foreground mb-5">{plan.description}</p>
                <button className={`w-full py-3 rounded-xl font-medium mb-6 transition motion-safe:active:scale-[0.97] ${
                  plan.featured
                    ? 'bg-primary text-primary-foreground hover:bg-primary/90'
                    : 'bg-muted text-foreground hover:bg-muted/80'
                }`}>
                  {plan.cta}
                </button>
                <ul className="space-y-2.5">
                  {plan.features.map((feature, fIndex) => (
                    <li key={fIndex} className="flex items-start gap-3">
                      <Check className="w-5 h-5 text-accent flex-shrink-0 mt-0.5" />
                      <span className="text-[0.9375rem] text-muted-foreground">{feature}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Hope + CTA */}
      <section className="relative overflow-hidden bg-gradient-to-br from-primary to-secondary py-16 text-white md:py-20">
        <div aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden">
          <div className="absolute -left-20 bottom-0 h-80 w-80 rounded-full bg-[#31D7C2]/20 blur-3xl animate-kio-drift" />
          <div className="absolute -right-16 -top-16 h-72 w-72 rounded-full bg-white/10 blur-3xl" />
        </div>

        <div className="relative mx-auto max-w-4xl px-4 text-center sm:px-6 lg:px-8">
          <Reveal className="flex justify-center">
            <KioMascot size={72} />
          </Reveal>
          <Reveal delay={90}>
            <p className="mt-5 font-handwritten text-4xl text-[#9BF3E7] sm:text-5xl">
              Every student deserves a space to be heard.
            </p>
            <h2 className="mt-5 text-[2.25rem] font-bold leading-tight sm:text-4xl md:text-5xl">
              Ready to support your students?
            </h2>
            <p className="mx-auto mt-4 max-w-2xl text-xl leading-relaxed text-blue-100">
              Start with one classroom, one family, one conversation. Kio grows with you.
            </p>
            <div className="mt-7 flex flex-col justify-center gap-4 sm:flex-row">
              <TransitionLink to="/login" className="px-8 py-4 bg-white text-primary rounded-xl text-[1.0625rem] font-medium hover:bg-blue-50 shadow-lg transition motion-safe:active:scale-[0.97]">
                Start Free
              </TransitionLink>
              <AnchorLink href="#pricing" className="px-8 py-4 bg-transparent border-2 border-white text-white rounded-xl text-[1.0625rem] font-medium hover:bg-white/10 transition motion-safe:active:scale-[0.97]">
                See plans
              </AnchorLink>
            </div>
          </Reveal>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-gray-900 text-gray-300 py-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid md:grid-cols-4 gap-8 mb-6">
            <div>
              <div className="flex items-center gap-2 mb-4">
                <KioLogo className="h-7 w-auto" reverse />
              </div>
              <p className="text-sm text-gray-400">
                AI-powered student wellness and parenting guidance platform.
              </p>
            </div>
            <div>
              <h4 className="font-semibold text-white mb-4">Product</h4>
              <ul className="space-y-2 text-sm">
                <li><AnchorLink href="#features" className="hover:text-white transition">Features</AnchorLink></li>
                <li><AnchorLink href="#pricing" className="hover:text-white transition">Pricing</AnchorLink></li>
                <li><TransitionLink to="/privacy" className="hover:text-white transition">Privacy</TransitionLink></li>
                <li><TransitionLink to="/terms" className="hover:text-white transition">Terms</TransitionLink></li>
              </ul>
            </div>
            <div>
              <h4 className="font-semibold text-white mb-4">Resources</h4>
              <ul className="space-y-2 text-sm">
                <li><a href="#" className="hover:text-white transition">Blog</a></li>
                <li><a href="#" className="hover:text-white transition">Help Center</a></li>
                <li><a href="#" className="hover:text-white transition">Community</a></li>
                <li><a href="#" className="hover:text-white transition">Contact</a></li>
              </ul>
            </div>
            <div>
              <h4 className="font-semibold text-white mb-4">Company</h4>
              <ul className="space-y-2 text-sm">
                <li><a href="#" className="hover:text-white transition">About</a></li>
                <li><a href="#" className="hover:text-white transition">Careers</a></li>
                <li><a href="#" className="hover:text-white transition">Partners</a></li>
                <li><a href="#" className="hover:text-white transition">Press</a></li>
              </ul>
            </div>
          </div>
          <div className="border-t border-gray-800 pt-8 text-sm text-gray-400 text-center">
            <p>&copy; 2026 Kio. All rights reserved. HIPAA, FERPA, and COPPA compliant.</p>
          </div>
        </div>
      </footer>
    </div>
  );
}
