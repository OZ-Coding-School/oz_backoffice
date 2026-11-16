import { expect, test } from '@playwright/test'

test('홈 화면이 뜬다', async ({ page }) => {
  await page.goto('/')
  await expect(page).toHaveTitle('오즈코딩스쿨 운영 행정 지원 플랫폼')
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('오즈코딩스쿨 운영 행정 지원 플랫폼')
})
