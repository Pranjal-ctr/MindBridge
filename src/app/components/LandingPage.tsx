import { Link } from 'react-router-dom';
import { Brain, Shield, Users, TrendingUp, MessageSquare, Heart, Lock, BarChart3, Calendar, ChevronRight, Check, Menu, X } from 'lucide-react';
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
              <Brain className="w-8 h-8 text-primary" />
              <span className="text-xl font-semibold text-foreground">MindBridge</span>
            </div>

            <nav className="hidden md:flex items-center gap-8">
              <a href="#features" className="text-muted-foreground hover:text-foreground transition">Features</a>
              <a href="#how-it-works" className="text-muted-foreground hover:text-foreground transition">How It Works</a>
              <a href="#pricing" className="text-muted-foreground hover:text-foreground transition">Pricing</a>
              <Link to="/login" className="text-muted-foreground hover:text-foreground transition">Sign In</Link>
              <Link to="/login" className="px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition">
                Start Free
              </Link>
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
              <a href="#features" className="text-muted-foreground hover:text-foreground transition">Features</a>
              <a href="#how-it-works" className="text-muted-foreground hover:text-foreground transition">How It Works</a>
              <a href="#pricing" className="text-muted-foreground hover:text-foreground transition">Pricing</a>
              <Link to="/login" className="text-muted-foreground hover:text-foreground transition">Sign In</Link>
              <Link to="/login" className="px-4 py-2 bg-primary text-primary-foreground rounded-lg text-center">
                Start Free
              </Link>
            </nav>
          </div>
        )}
      </header>

      {/* Hero Section */}
      <section className="relative overflow-hidden bg-gradient-to-br from-blue-50 via-white to-emerald-50 py-20 md:py-32">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid md:grid-cols-2 gap-12 items-center">
            <div>
              <h1 className="text-4xl md:text-5xl lg:text-6xl font-bold text-foreground mb-6 leading-tight">
                AI-Powered Support for Students and Parents
              </h1>
              <p className="text-xl text-muted-foreground mb-8 leading-relaxed">
                Early support, healthier relationships, and better outcomes through AI guidance and human expertise.
              </p>
              <div className="flex flex-col sm:flex-row gap-4">
                <Link to="/login" className="px-8 py-4 bg-primary text-primary-foreground rounded-xl font-medium hover:bg-primary/90 transition shadow-lg text-center">
                  Start Free
                </Link>
                <button className="px-8 py-4 bg-white text-primary border-2 border-primary rounded-xl font-medium hover:bg-blue-50 transition">
                  Book Demo
                </button>
              </div>
            </div>

            <div className="relative">
              <div className="bg-white rounded-2xl shadow-2xl p-8 border border-border">
                <div className="flex items-center gap-3 mb-6">
                  <div className="w-12 h-12 bg-gradient-to-br from-primary to-secondary rounded-full flex items-center justify-center">
                    <Brain className="w-6 h-6 text-white" />
                  </div>
                  <div>
                    <div className="font-medium">AI Wellness Companion</div>
                    <div className="text-sm text-muted-foreground">Available 24/7</div>
                  </div>
                </div>
                <div className="space-y-4">
                  <div className="bg-gradient-to-r from-blue-50 to-blue-100 rounded-xl p-4">
                    <p className="text-sm text-foreground">How can I help with exam stress?</p>
                  </div>
                  <div className="bg-gradient-to-r from-emerald-50 to-emerald-100 rounded-xl p-4">
                    <p className="text-sm text-foreground">I'm here for you. Let's explore some techniques together...</p>
                  </div>
                  <div className="flex gap-2">
                    <div className="px-4 py-2 bg-muted rounded-full text-sm">Study tips</div>
                    <div className="px-4 py-2 bg-muted rounded-full text-sm">Confidence</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* How It Works */}
      <section id="how-it-works" className="py-20 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <h2 className="text-3xl md:text-4xl font-bold text-foreground mb-4">How It Works</h2>
            <p className="text-xl text-muted-foreground max-w-2xl mx-auto">
              A comprehensive support system connecting students, parents, and counselors
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-8">
            <div className="text-center">
              <div className="w-16 h-16 bg-gradient-to-br from-blue-500 to-blue-600 rounded-2xl flex items-center justify-center mx-auto mb-6">
                <MessageSquare className="w-8 h-8 text-white" />
              </div>
              <h3 className="text-xl font-semibold mb-3">1. Students Chat with AI</h3>
              <p className="text-muted-foreground">
                Students share their concerns in a safe, private environment. AI provides immediate support and guidance.
              </p>
            </div>

            <div className="text-center">
              <div className="w-16 h-16 bg-gradient-to-br from-emerald-500 to-emerald-600 rounded-2xl flex items-center justify-center mx-auto mb-6">
                <TrendingUp className="w-8 h-8 text-white" />
              </div>
              <h3 className="text-xl font-semibold mb-3">2. Parents Get Insights</h3>
              <p className="text-muted-foreground">
                Parents receive actionable recommendations without seeing private conversations, respecting student privacy.
              </p>
            </div>

            <div className="text-center">
              <div className="w-16 h-16 bg-gradient-to-br from-purple-500 to-purple-600 rounded-2xl flex items-center justify-center mx-auto mb-6">
                <Users className="w-8 h-8 text-white" />
              </div>
              <h3 className="text-xl font-semibold mb-3">3. Counselors Intervene</h3>
              <p className="text-muted-foreground">
                When needed, professional counselors step in with AI-generated summaries for effective support.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Features */}
      <section id="features" className="py-20 bg-gradient-to-br from-gray-50 to-blue-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <h2 className="text-3xl md:text-4xl font-bold text-foreground mb-4">Features</h2>
            <p className="text-xl text-muted-foreground">Everything you need for student wellness</p>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8">
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
              <div key={index} className="bg-white rounded-2xl p-8 shadow-lg border border-border hover:shadow-xl transition">
                <div className={`w-12 h-12 bg-gradient-to-br ${feature.color} rounded-xl flex items-center justify-center mb-4`}>
                  <feature.icon className="w-6 h-6 text-white" />
                </div>
                <h3 className="text-xl font-semibold mb-3">{feature.title}</h3>
                <p className="text-muted-foreground">{feature.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Student Privacy Promise */}
      <section className="py-20 bg-white">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="bg-gradient-to-br from-blue-600 to-indigo-700 rounded-3xl p-12 text-white">
            <div className="flex items-center gap-3 mb-6">
              <Lock className="w-10 h-10" />
              <h2 className="text-3xl font-bold">Our Privacy Promise</h2>
            </div>
            <p className="text-xl mb-8 text-blue-100">
              We believe trust is the foundation of effective mental health support. That's why we built MindBridge with privacy at its core.
            </p>
            <div className="grid md:grid-cols-2 gap-6">
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
                  <span className="text-blue-50">{promise}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* Pricing */}
      <section id="pricing" className="py-20 bg-gradient-to-br from-gray-50 to-emerald-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <h2 className="text-3xl md:text-4xl font-bold text-foreground mb-4">Pricing</h2>
            <p className="text-xl text-muted-foreground">Choose the right plan for your needs</p>
          </div>

          <div className="grid md:grid-cols-3 gap-8 max-w-6xl mx-auto">
            {[
              {
                name: "Individual",
                price: "$19",
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
                price: "$12",
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
                  "White-label options",
                  "Advanced analytics",
                  "Custom AI training",
                  "SLA guarantees",
                  "On-premise deployment"
                ],
                cta: "Contact Sales",
                featured: false
              }
            ].map((plan, index) => (
              <div
                key={index}
                className={`bg-white rounded-2xl p-8 shadow-lg border-2 ${
                  plan.featured ? 'border-primary scale-105' : 'border-border'
                } hover:shadow-xl transition`}
              >
                {plan.featured && (
                  <div className="bg-primary text-primary-foreground text-sm font-medium px-3 py-1 rounded-full inline-block mb-4">
                    Most Popular
                  </div>
                )}
                <h3 className="text-2xl font-bold mb-2">{plan.name}</h3>
                <div className="mb-4">
                  <span className="text-4xl font-bold text-foreground">{plan.price}</span>
                  <span className="text-muted-foreground ml-2">{plan.period}</span>
                </div>
                <p className="text-muted-foreground mb-6">{plan.description}</p>
                <button className={`w-full py-3 rounded-xl font-medium mb-8 transition ${
                  plan.featured
                    ? 'bg-primary text-primary-foreground hover:bg-primary/90'
                    : 'bg-muted text-foreground hover:bg-muted/80'
                }`}>
                  {plan.cta}
                </button>
                <ul className="space-y-3">
                  {plan.features.map((feature, fIndex) => (
                    <li key={fIndex} className="flex items-start gap-3">
                      <Check className="w-5 h-5 text-accent flex-shrink-0 mt-0.5" />
                      <span className="text-sm text-muted-foreground">{feature}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-20 bg-gradient-to-br from-primary to-secondary text-white">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h2 className="text-3xl md:text-4xl font-bold mb-6">
            Ready to Support Your Students?
          </h2>
          <p className="text-xl text-blue-100 mb-8">
            Join hundreds of schools and thousands of families using MindBridge for student wellness.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link to="/login" className="px-8 py-4 bg-white text-primary rounded-xl font-medium hover:bg-blue-50 transition shadow-lg">
              Start Free Trial
            </Link>
            <button className="px-8 py-4 bg-transparent border-2 border-white text-white rounded-xl font-medium hover:bg-white/10 transition">
              Schedule Demo
            </button>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-gray-900 text-gray-300 py-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid md:grid-cols-4 gap-8 mb-8">
            <div>
              <div className="flex items-center gap-2 mb-4">
                <Brain className="w-6 h-6 text-primary" />
                <span className="font-semibold text-white">MindBridge</span>
              </div>
              <p className="text-sm text-gray-400">
                AI-powered student wellness and parenting guidance platform.
              </p>
            </div>
            <div>
              <h4 className="font-semibold text-white mb-4">Product</h4>
              <ul className="space-y-2 text-sm">
                <li><a href="#features" className="hover:text-white transition">Features</a></li>
                <li><a href="#pricing" className="hover:text-white transition">Pricing</a></li>
                <li><a href="#" className="hover:text-white transition">Security</a></li>
                <li><a href="#" className="hover:text-white transition">Privacy</a></li>
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
            <p>&copy; 2026 MindBridge. All rights reserved. HIPAA, FERPA, and COPPA compliant.</p>
          </div>
        </div>
      </footer>
    </div>
  );
}
