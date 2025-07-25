// supabase/functions/send-friend-invitation/index.ts
import { serve } from "https://deno.land/std@0.168.0/http/server.ts"
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'

const RESEND_API_KEY = Deno.env.get('RESEND_API_KEY')
const SUPABASE_URL = Deno.env.get('SUPABASE_URL')!
const SUPABASE_SERVICE_ROLE_KEY = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!

// Beautiful HTML email template for friend invitations
const createFriendInvitationEmailTemplate = (inviterName: string, friendEmail: string) => `
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>You're invited to join Jaydai!</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #374151;
            background-color: #f8fafc;
        }
        
        .container {
            max-width: 600px;
            margin: 0 auto;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 16px;
            overflow: hidden;
            box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1);
        }
        
        .header {
            padding: 40px 40px 0;
            text-align: center;
            color: white;
        }
        
        .logo {
            background: rgba(255, 255, 255, 0.2);
            width: 80px;
            height: 80px;
            border-radius: 20px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-size: 36px;
            font-weight: 700;
            margin-bottom: 24px;
            backdrop-filter: blur(10px);
        }
        
        .header h1 {
            font-size: 28px;
            font-weight: 700;
            margin-bottom: 12px;
        }
        
        .header p {
            font-size: 18px;
            opacity: 0.9;
            margin-bottom: 30px;
        }
        
        .content {
            background: white;
            padding: 40px;
            border-radius: 24px 24px 0 0;
            margin-top: 30px;
            position: relative;
        }
        
        .content::before {
            content: '';
            position: absolute;
            top: -10px;
            left: 50%;
            transform: translateX(-50%);
            width: 60px;
            height: 6px;
            background: rgba(255, 255, 255, 0.3);
            border-radius: 3px;
        }
        
        .invitation-message {
            text-align: center;
            margin-bottom: 32px;
        }
        
        .invitation-message h2 {
            color: #1f2937;
            font-size: 24px;
            font-weight: 600;
            margin-bottom: 16px;
        }
        
        .invitation-message p {
            font-size: 16px;
            color: #6b7280;
            margin-bottom: 8px;
        }
        
        .features {
            display: flex;
            justify-content: space-around;
            margin: 32px 0;
            padding: 24px;
            background: #f8fafc;
            border-radius: 16px;
        }
        
        .feature {
            text-align: center;
            flex: 1;
            padding: 0 16px;
        }
        
        .feature-icon {
            width: 48px;
            height: 48px;
            background: linear-gradient(135deg, #667eea, #764ba2);
            border-radius: 12px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            margin-bottom: 12px;
            font-size: 20px;
        }
        
        .feature h3 {
            font-size: 14px;
            font-weight: 600;
            color: #1f2937;
            margin-bottom: 4px;
        }
        
        .feature p {
            font-size: 12px;
            color: #6b7280;
        }
        
        .cta-button {
            display: inline-block;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            text-decoration: none;
            padding: 16px 32px;
            border-radius: 12px;
            font-weight: 600;
            font-size: 16px;
            text-align: center;
            margin: 24px 0;
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
            transition: transform 0.2s;
        }
        
        .cta-button:hover {
            transform: translateY(-2px);
        }
        
        .footer {
            text-align: center;
            padding: 32px 40px 40px;
            background: white;
        }
        
        .footer p {
            font-size: 14px;
            color: #9ca3af;
            margin-bottom: 16px;
        }
        
        .social-links {
            display: flex;
            justify-content: center;
            gap: 16px;
        }
        
        .social-link {
            width: 40px;
            height: 40px;
            background: #f3f4f6;
            border-radius: 10px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            text-decoration: none;
            color: #6b7280;
            transition: all 0.2s;
        }
        
        .social-link:hover {
            background: #e5e7eb;
            transform: translateY(-2px);
        }
        
        @media (max-width: 600px) {
            .container { margin: 20px; border-radius: 12px; }
            .header, .content, .footer { padding: 24px; }
            .features { flex-direction: column; gap: 20px; }
            .feature { padding: 0; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="logo">🚀</div>
            <h1>You're invited to Jaydai!</h1>
            <p>${inviterName} thinks you'll love our AI-powered productivity platform</p>
        </div>
        
        <div class="content">
            <div class="invitation-message">
                <h2>Ready to boost your productivity?</h2>
                <p><strong>${inviterName}</strong> has invited you to join Jaydai, the AI assistant that transforms how you work.</p>
                <p>Join thousands of professionals who are already saving hours every day with AI-powered templates and prompts.</p>
            </div>
            
            <div class="features">
                <div class="feature">
                    <div class="feature-icon">⚡</div>
                    <h3>Smart Templates</h3>
                    <p>Ready-to-use AI prompts for every task</p>
                </div>
                <div class="feature">
                    <div class="feature-icon">🎯</div>
                    <h3>Custom Blocks</h3>
                    <p>Build personalized AI workflows</p>
                </div>
                <div class="feature">
                    <div class="feature-icon">📈</div>
                    <h3>Boost Productivity</h3>
                    <p>Save hours on routine tasks</p>
                </div>
            </div>
            
            <div style="text-align: center;">
                <a href="https://jayd.ai/signup?ref=${encodeURIComponent(inviterName)}&invited_by=${encodeURIComponent(friendEmail)}" class="cta-button">
                    Join Jaydai for Free ✨
                </a>
                <p style="font-size: 14px; color: #9ca3af; margin-top: 16px;">
                    Free forever • No credit card required • Join in 30 seconds
                </p>
            </div>
        </div>
        
        <div class="footer">
            <p>This invitation was sent by ${inviterName} to ${friendEmail}</p>
            <p style="font-size: 12px; margin-top: 20px;">
                Jaydai - AI-powered productivity for professionals<br>
                <a href="https://jayd.ai" style="color: #667eea; text-decoration: none;">jayd.ai</a>
            </p>
            
            <div class="social-links">
                <a href="https://twitter.com/jaydai" class="social-link">🐦</a>
                <a href="https://linkedin.com/company/jaydai" class="social-link">💼</a>
                <a href="https://jayd.ai" class="social-link">🌐</a>
            </div>
        </div>
    </div>
</body>
</html>
`;

serve(async (req) => {
  try {
    const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

    // This function is triggered by database changes
    const { table, record, type } = await req.json()

    // Only process friend invitations
    if (table === 'share_invitations' && 
        type === 'INSERT' && 
        record.invitation_type === 'friend') {
      
      const { inviter_name, inviter_email, friend_email, id } = record

      // Send email using Resend
      const emailResponse = await fetch('https://api.resend.com/emails', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${RESEND_API_KEY}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          from: 'Jaydai Team <hello@jayd.ai>',
          to: [friend_email],
          subject: `${inviter_name} invited you to join Jaydai! 🚀`,
          html: createFriendInvitationEmailTemplate(inviter_name, friend_email),
        }),
      })

      const emailResult = await emailResponse.json()

      if (emailResponse.ok) {
        // Update invitation status to 'sent'
        await supabase
          .from('share_invitations')
          .update({ 
            status: 'sent', 
            sent_at: new Date().toISOString(),
            metadata: { email_id: emailResult.id }
          })
          .eq('id', id)

        return new Response(
          JSON.stringify({ success: true, message: 'Friend invitation email sent successfully' }),
          { headers: { 'Content-Type': 'application/json' } }
        )
      } else {
        // Update invitation status to 'failed'
        await supabase
          .from('share_invitations')
          .update({ 
            status: 'failed',
            metadata: { error: emailResult }
          })
          .eq('id', id)

        throw new Error(`Failed to send email: ${JSON.stringify(emailResult)}`)
      }
    }

    return new Response(
      JSON.stringify({ success: true, message: 'Function executed successfully' }),
      { headers: { 'Content-Type': 'application/json' } }
    )

  } catch (error) {
    console.error('Error in friend invitation function:', error)
    return new Response(
      JSON.stringify({ success: false, error: error.message }),
      { headers: { 'Content-Type': 'application/json' }, status: 500 }
    )
  }
})