// supabase/functions/send-friend-invitation/index.ts
import "jsr:@supabase/functions-js/edge-runtime.d.ts"
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'

// Internationalization content
const i18n = {
  en: {
    subject: (inviterName: string) => `${inviterName} invited you to the AI productivity platform that 1000+ users love! ⭐`,
    emailTitle: "Join the AI productivity revolution!",
    headerTitle: "You're invited to Jaydai!",
    headerSubtitle: (inviterName: string) => `${inviterName} wants you to experience the AI productivity revolution`,
    ratingBadge: "5-star rated",
    mainTitle: "Join 1000+ professionals saving hours daily",
    mainHighlight: (inviterName: string) => `${inviterName} thinks you'll love Jaydai's AI-powered productivity tools!`,
    mainDescription: "From complex prompts to instant templates, Jaydai transforms how you work with AI.",
    stats: {
      templates: "Ready Templates",
      users: "Active Users", 
      rating: "Store Rating"
    },
    features: {
      templates: {
        title: "1000+ AI Templates",
        description: "Access a massive library of professional AI prompts for every use case imaginable"
      },
      tracking: {
        title: "Track AI Usage", 
        description: "Monitor your AI interactions and optimize your productivity workflows"
      },
      prompts: {
        title: "Complex Prompts in Seconds",
        description: "Build sophisticated AI prompts instantly with our intuitive tools"
      },
      shortcuts: {
        title: "Keyboard Shortcuts",
        description: "Lightning-fast productivity with powerful keyboard shortcuts and tools"
      }
    },
    ctaTitle: "Ready to 10x your productivity?",
    ctaDescription: "Join the AI revolution that's transforming how professionals work",
    ctaButton: "Start Free Today 🚀",
    benefits: {
      free: "Free forever",
      noCard: "No credit card required", 
      quick: "Setup in 30 seconds"
    },
    footer: {
      invitation: (inviterName: string, friendEmail: string) => `This invitation was sent by <strong>${inviterName}</strong> to ${friendEmail}`,
      description: "Jaydai - The AI productivity platform trusted by 1000+ professionals<br>Rated ⭐⭐⭐⭐⭐ on app stores",
      links: {
        website: "Visit Website",
        templates: "Browse Templates", 
        features: "See Features"
      }
    }
  },
  fr: {
    subject: (inviterName: string) => `${inviterName} vous invite sur la plateforme IA que 1000+ utilisateurs adorent ! ⭐`,
    emailTitle: "Rejoignez la révolution de la productivité IA !",
    headerTitle: "Vous êtes invité(e) sur Jaydai !",
    headerSubtitle: (inviterName: string) => `${inviterName} souhaite vous faire découvrir la révolution de la productivité IA`,
    ratingBadge: "Noté 5 étoiles",
    mainTitle: "Rejoignez 1000+ professionnels qui économisent des heures chaque jour",
    mainHighlight: (inviterName: string) => `${inviterName} pense que vous allez adorer les outils de productivité IA de Jaydai !`,
    mainDescription: "Des prompts complexes aux modèles instantanés, Jaydai transforme votre façon de travailler avec l'IA.",
    stats: {
      templates: "Modèles Prêts",
      users: "Utilisateurs Actifs",
      rating: "Note Store"
    },
    features: {
      templates: {
        title: "1000+ Modèles IA",
        description: "Accédez à une bibliothèque massive de prompts IA professionnels pour tous les cas d'usage"
      },
      tracking: {
        title: "Suivi Usage IA",
        description: "Surveillez vos interactions IA et optimisez vos workflows de productivité"
      },
      prompts: {
        title: "Prompts Complexes en Secondes",
        description: "Créez des prompts IA sophistiqués instantanément avec nos outils intuitifs"
      },
      shortcuts: {
        title: "Raccourcis Clavier",
        description: "Productivité ultra-rapide avec des raccourcis clavier et outils puissants"
      }
    },
    ctaTitle: "Prêt(e) à multiplier votre productivité par 10 ?",
    ctaDescription: "Rejoignez la révolution IA qui transforme le travail des professionnels",
    ctaButton: "Commencer Gratuitement 🚀",
    benefits: {
      free: "Gratuit à vie",
      noCard: "Aucune carte requise",
      quick: "Configuration en 30 secondes"
    },
    footer: {
      invitation: (inviterName: string, friendEmail: string) => `Cette invitation a été envoyée par <strong>${inviterName}</strong> à ${friendEmail}`,
      description: "Jaydai - La plateforme de productivité IA approuvée par 1000+ professionnels<br>Notée ⭐⭐⭐⭐⭐ sur les stores",
      links: {
        website: "Visiter le Site",
        templates: "Parcourir les Modèles",
        features: "Voir les Fonctionnalités"
      }
    }
  }
}

Deno.serve(async (req) => {
  try {
    const supabase = createClient(
      Deno.env.get('SUPABASE_URL')!,
      Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!
    )

    const { record, locale = 'en' } = await req.json()
    
    // Validate locale
    const lang = ['en', 'fr'].includes(locale) ? locale : 'en'
    const content = i18n[lang]

    const SENDGRID_API_KEY = Deno.env.get("SENDGRID_API_KEY")!
    const FROM_EMAIL = "system@jayd.ai"
    
    // Only process friend invitations
    if (record.invitation_type === 'friend') {
      const { inviter_name, inviter_email, friend_email, id } = record

      // Send friend invitation email using SendGrid
      const emailResponse = await sendEmail({
        to: friend_email,
        from: FROM_EMAIL,
        subject: content.subject(inviter_name),
        content: createFriendInvitationEmailTemplate(inviter_name, friend_email, content),
        replyTo: inviter_email
      }, SENDGRID_API_KEY)

      if (emailResponse.ok) {
        // Update invitation status to 'sent'
        await supabase
          .from('share_invitations')
          .update({ 
            status: 'sent', 
            sent_at: new Date().toISOString(),
            metadata: { email_sent_via: 'sendgrid', locale: lang }
          })
          .eq('id', id)

        console.log(`✅ Friend invitation sent successfully to ${friend_email} in ${lang}`)
        return new Response(`Friend invitation email sent successfully in ${lang}`, { status: 200 })
      } else {
        const errorText = await emailResponse.text()
        console.error("SendGrid error:", errorText)
        
        // Update invitation status to 'failed'
        await supabase
          .from('share_invitations')
          .update({ 
            status: 'failed',
            metadata: { error: errorText, locale: lang }
          })
          .eq('id', id)

        return new Response(`SendGrid error: ${errorText}`, { status: 500 })
      }
    }

    return new Response("Function executed successfully", { status: 200 })

  } catch (error) {
    console.error('Error in friend invitation function:', error)
    return new Response(`Error: ${error.message}`, { status: 500 })
  }
})

// Helper function to send email via SendGrid
async function sendEmail({ to, from, subject, content, replyTo }, apiKey) {
  const emailData: Record<string, any> = {
    personalizations: [{ to: [{ email: to }] }],
    from: { email: from, name: "Jaydai Team" },
    subject,
    content: [{ type: "text/html", value: content }],
  }

  if (replyTo) {
    emailData.reply_to = { email: replyTo }
  }

  return await fetch("https://api.sendgrid.com/v3/mail/send", {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${apiKey}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(emailData),
  })
}

// Beautiful HTML email template for friend invitations with i18n support
function createFriendInvitationEmailTemplate(inviterName: string, friendEmail: string, content: any) {
  return `
<!DOCTYPE html>
<html lang="${content === i18n.fr ? 'fr' : 'en'}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="color-scheme" content="light dark">
    <meta name="supported-color-schemes" content="light dark">
    <title>${content.emailTitle}</title>
    <style>
        :root {
            color-scheme: light dark;
            supported-color-schemes: light dark;
        }
        
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #1f2937;
            background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%);
            padding: 20px;
        }
        
        .container {
            max-width: 650px;
            margin: 0 auto;
            background: white;
            border-radius: 20px;
            overflow: hidden;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
            border: 1px solid rgba(255, 255, 255, 0.2);
        }
        
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 50px 40px 40px;
            text-align: center;
            color: white;
            position: relative;
            overflow: hidden;
        }
        
        .header::before {
            content: '';
            position: absolute;
            top: -50%;
            left: -50%;
            width: 200%;
            height: 200%;
            background: url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23ffffff' fill-opacity='0.05'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E") repeat;
            opacity: 0.1;
            animation: float 20s ease-in-out infinite;
        }
        
        @keyframes float {
            0%, 100% { transform: translateY(0px) rotate(0deg); }
            50% { transform: translateY(-20px) rotate(5deg); }
        }
        
        .logo {
            background: rgba(255, 255, 255, 0.15);
            width: 90px;
            height: 90px;
            border-radius: 22px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            margin-bottom: 24px;
            backdrop-filter: blur(20px);
            border: 2px solid rgba(255, 255, 255, 0.2);
            position: relative;
            z-index: 1;
            overflow: hidden;
        }
        
        .logo img {
            width: 60px;
            height: 60px;
            object-fit: contain;
        }
        
        .header h1 {
            font-size: 32px;
            font-weight: 700;
            margin-bottom: 12px;
            position: relative;
            z-index: 1;
        }
        
        .header .subtitle {
            font-size: 18px;
            opacity: 0.95;
            margin-bottom: 16px;
            position: relative;
            z-index: 1;
        }
        
        .rating-badge {
            display: inline-flex;
            align-items: center;
            background: rgba(255, 255, 255, 0.2);
            padding: 8px 16px;
            border-radius: 25px;
            backdrop-filter: blur(10px);
            margin-top: 12px;
            position: relative;
            z-index: 1;
        }
        
        .rating-badge .stars {
            color: #fbbf24;
            margin-right: 8px;
            font-size: 16px;
        }
        
        .content {
            padding: 50px 40px;
        }
        
        .invitation-message {
            text-align: center;
            margin-bottom: 40px;
        }
        
        .invitation-message h2 {
            color: #1f2937;
            font-size: 28px;
            font-weight: 700;
            margin-bottom: 16px;
            background: linear-gradient(135deg, #667eea, #764ba2);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        
        .invitation-message .highlight {
            font-size: 18px;
            color: #4b5563;
            margin-bottom: 12px;
            font-weight: 500;
        }
        
        .invitation-message p {
            font-size: 16px;
            color: #6b7280;
            margin-bottom: 8px;
        }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 20px;
            margin: 40px 0;
            padding: 30px;
            background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%);
            border-radius: 20px;
            border: 1px solid #e5e7eb;
        }
        
        .stat {
            text-align: center;
        }
        
        .stat-number {
            font-size: 28px;
            font-weight: 700;
            color: #667eea;
            margin-bottom: 8px;
            display: block;
        }
        
        .stat-label {
            font-size: 14px;
            font-weight: 500;
            color: #6b7280;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        .features {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 24px;
            margin: 40px 0;
        }
        
        .feature {
            padding: 24px;
            background: white;
            border-radius: 16px;
            border: 2px solid #f3f4f6;
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
        }
        
        .feature:hover {
            border-color: #667eea;
            transform: translateY(-2px);
            box-shadow: 0 10px 25px -5px rgba(102, 126, 234, 0.15);
        }
        
        .feature::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 3px;
            background: linear-gradient(135deg, #667eea, #764ba2);
        }
        
        .feature-icon {
            width: 50px;
            height: 50px;
            background: linear-gradient(135deg, #667eea, #764ba2);
            border-radius: 14px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            margin-bottom: 16px;
            font-size: 22px;
            box-shadow: 0 8px 16px -4px rgba(102, 126, 234, 0.3);
        }
        
        .feature h3 {
            font-size: 16px;
            font-weight: 600;
            color: #1f2937;
            margin-bottom: 8px;
        }
        
        .feature p {
            font-size: 14px;
            color: #6b7280;
            line-height: 1.5;
        }
        
        .cta-section {
            text-align: center;
            margin: 40px 0;
            padding: 0;
            background: url('https://vetoswvwgsebhxetqppa.supabase.co/storage/v1/object/public/images/organizations/jaydai_banner.png') center/cover;
            border-radius: 20px;
            color: white;
            position: relative;
            overflow: hidden;
            min-height: 300px;
            display: flex;
            flex-direction: column;
            justify-content: center;
        }
        
        .cta-section::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: linear-gradient(135deg, rgba(102, 126, 234, 0.85) 0%, rgba(118, 75, 162, 0.85) 100%);
            z-index: 1;
        }
        
        .cta-content {
            position: relative;
            z-index: 2;
            padding: 40px;
        }
        
        .cta-section h3 {
            font-size: 24px;
            font-weight: 700;
            margin-bottom: 12px;
            position: relative;
            z-index: 2;
        }
        
        .cta-section p {
            font-size: 16px;
            opacity: 0.95;
            margin-bottom: 24px;
            position: relative;
            z-index: 2;
        }
        
        .cta-button {
            display: inline-block;
            background: white;
            color: #667eea;
            text-decoration: none;
            padding: 18px 40px;
            border-radius: 14px;
            font-weight: 700;
            font-size: 16px;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.2);
            transition: all 0.3s ease;
            position: relative;
            z-index: 2;
        }
        
        .cta-button:hover {
            transform: translateY(-3px);
            box-shadow: 0 15px 35px -5px rgba(0, 0, 0, 0.3);
        }
        
        .benefits {
            display: flex;
            justify-content: center;
            gap: 30px;
            margin-top: 20px;
            flex-wrap: wrap;
            position: relative;
            z-index: 2;
        }
        
        .benefit {
            display: flex;
            align-items: center;
            font-size: 14px;
            opacity: 0.9;
        }
        
        .benefit::before {
            content: '✓';
            margin-right: 8px;
            font-weight: bold;
            color: #10b981;
        }
        
        .footer {
            text-align: center;
            padding: 40px;
            background: #f8fafc;
            border-top: 1px solid #e5e7eb;
        }
        
        .footer p {
            font-size: 14px;
            color: #9ca3af;
            margin-bottom: 16px;
        }
        
        .footer-links {
            display: flex;
            justify-content: center;
            gap: 20px;
            margin-top: 20px;
        }
        
        .footer-link {
            color: #667eea;
            text-decoration: none;
            font-size: 14px;
            font-weight: 500;
            transition: opacity 0.2s;
        }
        
        .footer-link:hover {
            opacity: 0.7;
        }
        
        @media (max-width: 600px) {
            body { padding: 10px; }
            .container { border-radius: 16px; }
            .header, .content, .footer { padding: 30px 24px; }
            .cta-content { padding: 30px 24px; }
            .stats-grid { grid-template-columns: 1fr; gap: 16px; padding: 24px; }
            .features { grid-template-columns: 1fr; gap: 16px; }
            .benefits { flex-direction: column; gap: 12px; }
            .header h1 { font-size: 26px; }
            .invitation-message h2 { font-size: 22px; }
        }

        @media (prefers-color-scheme: dark) {
            body { background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); }
            .container { background: #1e293b; border-color: rgba(255, 255, 255, 0.1); }
            .content { color: #f1f5f9; }
            .invitation-message h2 { color: #f1f5f9; }
            .invitation-message .highlight { color: #cbd5e1; }
            .invitation-message p { color: #94a3b8; }
            .stats-grid { background: linear-gradient(135deg, #334155 0%, #475569 100%); border-color: #475569; }
            .stat-label { color: #94a3b8; }
            .feature { background: #334155; border-color: #475569; }
            .feature h3 { color: #f1f5f9; }
            .feature p { color: #94a3b8; }
            .footer { background: #0f172a; border-color: #334155; }
            .footer p { color: #64748b; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="logo">
                <img src="https://vetoswvwgsebhxetqppa.supabase.co/storage/v1/object/public/images/organizations/jaydai_org_logo.png" alt="Jaydai Logo" />
            </div>
            <h1>${content.headerTitle}</h1>
            <p class="subtitle">${content.headerSubtitle(inviterName)}</p>
            <div class="rating-badge">
                <span class="stars">⭐⭐⭐⭐⭐</span>
                <span>${content.ratingBadge}</span>
            </div>
        </div>
        
        <div class="content">
            <div class="invitation-message">
                <h2>${content.mainTitle}</h2>
                <p class="highlight">${content.mainHighlight(inviterName)}</p>
                <p>${content.mainDescription}</p>
            </div>
            
            <div class="stats-grid">
                <div class="stat">
                    <span class="stat-number">1000+</span>
                    <span class="stat-label">${content.stats.templates}</span>
                </div>
                <div class="stat">
                    <span class="stat-number">1000+</span>
                    <span class="stat-label">${content.stats.users}</span>
                </div>
                <div class="stat">
                    <span class="stat-number">5⭐</span>
                    <span class="stat-label">${content.stats.rating}</span>
                </div>
            </div>
            
            <div class="features">
                <div class="feature">
                    <div class="feature-icon">⚡</div>
                    <h3>${content.features.templates.title}</h3>
                    <p>${content.features.templates.description}</p>
                </div>
                <div class="feature">
                    <div class="feature-icon">📊</div>
                    <h3>${content.features.tracking.title}</h3>
                    <p>${content.features.tracking.description}</p>
                </div>
                <div class="feature">
                    <div class="feature-icon">🛠️</div>
                    <h3>${content.features.prompts.title}</h3>
                    <p>${content.features.prompts.description}</p>
                </div>
                <div class="feature">
                    <div class="feature-icon">⌨️</div>
                    <h3>${content.features.shortcuts.title}</h3>
                    <p>${content.features.shortcuts.description}</p>
                </div>
            </div>
            
            <div class="cta-section">
                <div class="cta-content">
                    <h3>${content.ctaTitle}</h3>
                    <p>${content.ctaDescription}</p>
                    <a href="https://jayd.ai?ref=${encodeURIComponent(inviterName)}&invited_by=${encodeURIComponent(friendEmail)}" class="cta-button">
                        ${content.ctaButton}
                    </a>
                    <div class="benefits">
                        <div class="benefit">${content.benefits.free}</div>
                        <div class="benefit">${content.benefits.noCard}</div>
                        <div class="benefit">${content.benefits.quick}</div>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="footer">
            <p>${content.footer.invitation(inviterName, friendEmail)}</p>
            <p style="font-size: 12px; margin-top: 24px;">
                ${content.footer.description}
            </p>
            
            <div class="footer-links">
                <a href="https://jayd.ai" class="footer-link">${content.footer.links.website}</a>
                <a href="https://jayd.ai/templates" class="footer-link">${content.footer.links.templates}</a>
                <a href="https://jayd.ai/features" class="footer-link">${content.footer.links.features}</a>
            </div>
        </div>
    </div>
</body>
</html>
`
}