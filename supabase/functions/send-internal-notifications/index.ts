// supabase/functions/send-internal-notifications/index.ts
import "jsr:@supabase/functions-js/edge-runtime.d.ts"
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'

console.log("Internal Notifications Function Started!")

Deno.serve(async (req) => {
  try {
    const supabase = createClient(
      Deno.env.get('SUPABASE_URL')!,
      Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!
    )

    const { record } = await req.json()

    const SENDGRID_API_KEY = Deno.env.get("SENDGRID_API_KEY")!
    const FROM_EMAIL = "system@jayd.ai"
    const CONTACT_EMAIL = "contact@jayd.ai"
    
    // Process team invitation and referral program requests
    if (record.invitation_type === 'team' || record.invitation_type === 'referral') {
      const { inviter_name, inviter_email, invitation_type, id } = record

      let emailTemplate = ''
      let subject = ''

      if (invitation_type === 'team') {
        emailTemplate = createTeamInvitationEmailTemplate(inviter_name, inviter_email)
        subject = `🏢 Team Invitation Request from ${inviter_name}`
      } else if (invitation_type === 'referral') {
        emailTemplate = createReferralProgramEmailTemplate(inviter_name, inviter_email)
        subject = `🎁 Referral Program Request from ${inviter_name}`
      }

      // Send internal notification email using SendGrid
      const emailResponse = await sendEmail({
        to: CONTACT_EMAIL,
        from: FROM_EMAIL,
        subject: subject,
        content: emailTemplate,
        replyTo: inviter_email
      }, SENDGRID_API_KEY)

      if (emailResponse.ok) {
        // Update invitation status to 'sent'
        await supabase
          .from('share_invitations')
          .update({ 
            status: 'sent', 
            sent_at: new Date().toISOString(),
            metadata: { 
              email_sent_via: 'sendgrid',
              notification_sent: true 
            }
          })
          .eq('id', id)

        console.log(`✅ ${invitation_type} notification sent successfully for user:`, inviter_email)
        return new Response(`${invitation_type} notification sent successfully`, { status: 200 })
      } else {
        const errorText = await emailResponse.text()
        console.error("SendGrid error:", errorText)
        
        // Update invitation status to 'failed'
        await supabase
          .from('share_invitations')
          .update({ 
            status: 'failed',
            metadata: { error: errorText }
          })
          .eq('id', id)

        return new Response(`SendGrid error: ${errorText}`, { status: 500 })
      }
    }

    return new Response("Function executed successfully", { status: 200 })

  } catch (error) {
    console.error('Error in internal notifications function:', error)
    return new Response(`Error: ${error.message}`, { status: 500 })
  }
})

// Helper function to send email via SendGrid (same pattern as your existing function)
async function sendEmail({ to, from, subject, content, replyTo }, apiKey) {
  const emailData = {
    personalizations: [{ to: [{ email: to }] }],
    from: { email: from, name: "Jaydai System" },
    subject: subject,
    content: [{ type: "text/html", value: content }],
  }

  // Add reply-to if provided
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

// Email template for team invitation requests
function createTeamInvitationEmailTemplate(userName: string, userEmail: string) {
  return `
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="color-scheme" content="light dark">
    <meta name="supported-color-schemes" content="light dark">
    <title>Team Invitation Request</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        
        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #374151;
            background-color: #f8fafc;
            margin: 0;
            padding: 40px 20px;
        }
        
        .container {
            max-width: 600px;
            margin: 0 auto;
            background: white;
            border-radius: 16px;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.1);
            overflow: hidden;
        }
        
        .header {
            background: linear-gradient(135deg, #059669 0%, #047857 100%);
            padding: 40px;
            color: white;
            text-align: center;
        }
        
        .header h1 {
            font-size: 24px;
            font-weight: 700;
            margin: 0 0 12px;
        }
        
        .header p {
            opacity: 0.9;
            margin: 0;
        }
        
        .content {
            padding: 40px;
        }
        
        .user-info {
            background: #f8fafc;
            padding: 24px;
            border-radius: 12px;
            margin-bottom: 32px;
            border-left: 4px solid #059669;
        }
        
        .user-info h3 {
            color: #1f2937;
            font-size: 18px;
            font-weight: 600;
            margin-bottom: 16px;
        }
        
        .info-row {
            display: flex;
            margin-bottom: 8px;
        }
        
        .info-label {
            font-weight: 600;
            color: #374151;
            min-width: 120px;
        }
        
        .info-value {
            color: #6b7280;
        }
        
        .action-required {
            background: #fef3c7;
            border: 2px solid #f59e0b;
            border-radius: 12px;
            padding: 20px;
            margin: 24px 0;
        }
        
        .action-required h4 {
            color: #92400e;
            font-weight: 600;
            margin-bottom: 8px;
        }
        
        .action-required p {
            color: #b45309;
            margin: 0;
        }
        
        .footer {
            background: #f9fafb;
            padding: 24px 40px;
            color: #6b7280;
            font-size: 14px;
            text-align: center;
        }

        @media (prefers-color-scheme: dark) {
            body { background-color: #1a1b21; color: #eaeaea; }
            .container { background: #1a1b21; }
            .content { background: #1a1b21; }
            .user-info { background: #252729; border-left-color: #10b981; }
            .user-info h3 { color: #f9fafb; }
            .info-label { color: #d1d5db; }
            .info-value { color: #9ca3af; }
            .action-required { background: rgba(251, 191, 36, 0.1); border-color: rgba(251, 191, 36, 0.3); }
            .action-required h4 { color: #fbbf24; }
            .action-required p { color: #f59e0b; }
            .footer { background: #252729; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🏢 Team Invitation Request</h1>
            <p>A user wants to invite their team to Jaydai</p>
        </div>
        
        <div class="content">
            <div class="user-info">
                <h3>User Details</h3>
                <div class="info-row">
                    <div class="info-label">Name:</div>
                    <div class="info-value">${userName}</div>
                </div>
                <div class="info-row">
                    <div class="info-label">Email:</div>
                    <div class="info-value">${userEmail}</div>
                </div>
                <div class="info-row">
                    <div class="info-label">Request Date:</div>
                    <div class="info-value">${new Date().toLocaleDateString('en-US', { 
                        year: 'numeric', 
                        month: 'long', 
                        day: 'numeric', 
                        hour: '2-digit', 
                        minute: '2-digit'
                    })}</div>
                </div>
            </div>
            
            <div class="action-required">
                <h4>Action Required</h4>
                <p>Please reach out to this user to discuss team invitation options and pricing.</p>
            </div>
            
            <p><strong>Suggested next steps:</strong></p>
            <ul style="color: #6b7280; margin-left: 20px;">
                <li>Send a personalized follow-up email within 24 hours</li>
                <li>Schedule a brief call to understand their team size and needs</li>
                <li>Provide custom pricing and onboarding options</li>
                <li>Share team management resources and best practices</li>
            </ul>
        </div>
        
        <div class="footer">
            <p>This notification was automatically generated from Jaydai's sharing system.</p>
        </div>
    </div>
</body>
</html>
`
}

// Email template for referral program requests
function createReferralProgramEmailTemplate(userName: string, userEmail: string) {
  return `
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="color-scheme" content="light dark">
    <meta name="supported-color-schemes" content="light dark">
    <title>Referral Program Request</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        
        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #374151;
            background-color: #f8fafc;
            margin: 0;
            padding: 40px 20px;
        }
        
        .container {
            max-width: 600px;
            margin: 0 auto;
            background: white;
            border-radius: 16px;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.1);
            overflow: hidden;
        }
        
        .header {
            background: linear-gradient(135deg, #7c3aed 0%, #5b21b6 100%);
            padding: 40px;
            color: white;
            text-align: center;
        }
        
        .header h1 {
            font-size: 24px;
            font-weight: 700;
            margin: 0 0 12px;
        }
        
        .header p {
            opacity: 0.9;
            margin: 0;
        }
        
        .content {
            padding: 40px;
        }
        
        .user-info {
            background: #faf5ff;
            padding: 24px;
            border-radius: 12px;
            margin-bottom: 32px;
            border-left: 4px solid #7c3aed;
        }
        
        .user-info h3 {
            color: #1f2937;
            font-size: 18px;
            font-weight: 600;
            margin-bottom: 16px;
        }
        
        .info-row {
            display: flex;
            margin-bottom: 8px;
        }
        
        .info-label {
            font-weight: 600;
            color: #374151;
            min-width: 120px;
        }
        
        .info-value {
            color: #6b7280;
        }
        
        .action-required {
            background: #fef3c7;
            border: 2px solid #f59e0b;
            border-radius: 12px;
            padding: 20px;
            margin: 24px 0;
        }
        
        .action-required h4 {
            color: #92400e;
            font-weight: 600;
            margin-bottom: 8px;
        }
        
        .action-required p {
            color: #b45309;
            margin: 0;
        }
        
        .footer {
            background: #f9fafb;
            padding: 24px 40px;
            color: #6b7280;
            font-size: 14px;
            text-align: center;
        }

        @media (prefers-color-scheme: dark) {
            body { background-color: #1a1b21; color: #eaeaea; }
            .container { background: #1a1b21; }
            .content { background: #1a1b21; }
            .user-info { background: rgba(124, 58, 237, 0.1); border-left-color: #a855f7; }
            .user-info h3 { color: #f9fafb; }
            .info-label { color: #d1d5db; }
            .info-value { color: #9ca3af; }
            .action-required { background: rgba(251, 191, 36, 0.1); border-color: rgba(251, 191, 36, 0.3); }
            .action-required h4 { color: #fbbf24; }
            .action-required p { color: #f59e0b; }
            .footer { background: #252729; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎁 Referral Program Request</h1>
            <p>A user wants to join the referral program</p>
        </div>
        
        <div class="content">
            <div class="user-info">
                <h3>User Details</h3>
                <div class="info-row">
                    <div class="info-label">Name:</div>
                    <div class="info-value">${userName}</div>
                </div>
                <div class="info-row">
                    <div class="info-label">Email:</div>
                    <div class="info-value">${userEmail}</div>
                </div>
                <div class="info-row">
                    <div class="info-label">Request Date:</div>
                    <div class="info-value">${new Date().toLocaleDateString('en-US', { 
                        year: 'numeric', 
                        month: 'long', 
                        day: 'numeric', 
                        hour: '2-digit', 
                        minute: '2-digit'
                    })}</div>
                </div>
            </div>
            
            <div class="action-required">
                <h4>Action Required</h4>
                <p>This user wants to become a referral partner and earn rewards for bringing new users to Jaydai.</p>
            </div>
            
            <p><strong>Suggested next steps:</strong></p>
            <ul style="color: #6b7280; margin-left: 20px;">
                <li>Review user's profile and engagement level</li>
                <li>Send referral program details and commission structure</li>
                <li>Set up their unique referral code and tracking</li>
                <li>Provide marketing materials and best practices</li>
                <li>Schedule onboarding call if they're a high-value referrer</li>
            </ul>
            
            <p style="margin-top: 24px; padding: 16px; background: #ecfdf5; border-radius: 8px; color: #065f46; font-size: 14px;">
                <strong>💡 Pro Tip:</strong> Users who request referral access are often your most engaged advocates. Consider fast-tracking their application!
            </p>
        </div>
        
        <div class="footer">
            <p>This notification was automatically generated from Jaydai's sharing system.</p>
        </div>
    </div>
</body>
</html>
`
}// supabase/functions/send-internal-notifications/index.ts
import { serve } from "https://deno.land/std@0.168.0/http/server.ts"
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'

const RESEND_API_KEY = Deno.env.get('RESEND_API_KEY')
const SUPABASE_URL = Deno.env.get('SUPABASE_URL')!
const SUPABASE_SERVICE_ROLE_KEY = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!

// Email template for team invitation requests
const createTeamInvitationEmailTemplate = (userName: string, userEmail: string) => `
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Team Invitation Request</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        
        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #374151;
            background-color: #f8fafc;
            margin: 0;
            padding: 40px 20px;
        }
        
        .container {
            max-width: 600px;
            margin: 0 auto;
            background: white;
            border-radius: 16px;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.1);
            overflow: hidden;
        }
        
        .header {
            background: linear-gradient(135deg, #059669 0%, #047857 100%);
            padding: 40px;
            color: white;
            text-align: center;
        }
        
        .header h1 {
            font-size: 24px;
            font-weight: 700;
            margin: 0 0 12px;
        }
        
        .header p {
            opacity: 0.9;
            margin: 0;
        }
        
        .content {
            padding: 40px;
        }
        
        .user-info {
            background: #f8fafc;
            padding: 24px;
            border-radius: 12px;
            margin-bottom: 32px;
            border-left: 4px solid #059669;
        }
        
        .user-info h3 {
            color: #1f2937;
            font-size: 18px;
            font-weight: 600;
            margin-bottom: 16px;
        }
        
        .info-row {
            display: flex;
            margin-bottom: 8px;
        }
        
        .info-label {
            font-weight: 600;
            color: #374151;
            min-width: 120px;
        }
        
        .info-value {
            color: #6b7280;
        }
        
        .action-required {
            background: #fef3c7;
            border: 2px solid #f59e0b;
            border-radius: 12px;
            padding: 20px;
            margin: 24px 0;
        }
        
        .action-required h4 {
            color: #92400e;
            font-weight: 600;
            margin-bottom: 8px;
        }
        
        .action-required p {
            color: #b45309;
            margin: 0;
        }
        
        .cta-button {
            display: inline-block;
            background: linear-gradient(135deg, #059669 0%, #047857 100%);
            color: white;
            text-decoration: none;
            padding: 12px 24px;
            border-radius: 8px;
            font-weight: 600;
            margin: 16px 0;
        }
        
        .footer {
            background: #f9fafb;
            padding: 24px 40px;
            color: #6b7280;
            font-size: 14px;
            text-align: center;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🏢 Team Invitation Request</h1>
            <p>A user wants to invite their team to Jaydai</p>
        </div>
        
        <div class="content">
            <div class="user-info">
                <h3>User Details</h3>
                <div class="info-row">
                    <div class="info-label">Name:</div>
                    <div class="info-value">${userName}</div>
                </div>
                <div class="info-row">
                    <div class="info-label">Email:</div>
                    <div class="info-value">${userEmail}</div>
                </div>
                <div class="info-row">
                    <div class="info-label">Request Date:</div>
                    <div class="info-value">${new Date().toLocaleDateString('en-US', { 
                        year: 'numeric', 
                        month: 'long', 
                        day: 'numeric', 
                        hour: '2-digit', 
                        minute: '2-digit'
                    })}</div>
                </div>
            </div>
            
            <div class="action-required">
                <h4>Action Required</h4>
                <p>This user wants to become a referral partner and earn rewards for bringing new users to Jaydai.</p>
            </div>
            
            <p><strong>Suggested next steps:</strong></p>
            <ul style="color: #6b7280; margin-left: 20px;">
                <li>Review user's profile and engagement level</li>
                <li>Send referral program details and commission structure</li>
                <li>Set up their unique referral code and tracking</li>
                <li>Provide marketing materials and best practices</li>
                <li>Schedule onboarding call if they're a high-value referrer</li>
            </ul>
            
            <p style="margin-top: 24px; padding: 16px; background: #ecfdf5; border-radius: 8px; color: #065f46; font-size: 14px;">
                <strong>💡 Pro Tip:</strong> Users who request referral access are often your most engaged advocates. Consider fast-tracking their application!
            </p>
        </div>
        
        <div class="footer">
            <p>This notification was automatically generated from Jaydai's sharing system.</p>
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

    // Process team invitation and referral program requests
    if (table === 'share_invitations' && 
        type === 'INSERT' && 
        (record.invitation_type === 'team' || record.invitation_type === 'referral')) {
      
      const { inviter_name, inviter_email, invitation_type, id } = record

      let emailTemplate = ''
      let subject = ''

      if (invitation_type === 'team') {
        emailTemplate = createTeamInvitationEmailTemplate(inviter_name, inviter_email)
        subject = `🏢 Team Invitation Request from ${inviter_name}`
      } else if (invitation_type === 'referral') {
        emailTemplate = createReferralProgramEmailTemplate(inviter_name, inviter_email)
        subject = `🎁 Referral Program Request from ${inviter_name}`
      }

      // Send internal notification email
      const emailResponse = await fetch('https://api.resend.com/emails', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${RESEND_API_KEY}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          from: 'Jaydai System <system@jayd.ai>',
          to: ['contact@jayd.ai'],
          subject: subject,
          html: emailTemplate,
          // Add reply-to for easy follow-up
          reply_to: inviter_email,
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
            metadata: { 
              email_id: emailResult.id,
              notification_sent: true 
            }
          })
          .eq('id', id)

        console.log(`✅ ${invitation_type} notification sent successfully for user:`, inviter_email)

        return new Response(
          JSON.stringify({ 
            success: true, 
            message: `${invitation_type} notification sent successfully`,
            email_id: emailResult.id
          }),
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

        throw new Error(`Failed to send ${invitation_type} notification: ${JSON.stringify(emailResult)}`)
      }
    }

    return new Response(
      JSON.stringify({ success: true, message: 'Function executed successfully' }),
      { headers: { 'Content-Type': 'application/json' } }
    )

  } catch (error) {
    console.error('Error in internal notifications function:', error)
    return new Response(
      JSON.stringify({ success: false, error: error.message }),
      { headers: { 'Content-Type': 'application/json' }, status: 500 }
    )
  }
})