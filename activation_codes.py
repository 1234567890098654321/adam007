#!/usr/bin/env python3
"""
ملف إدارة أكواد التفعيل - للمطور فقط
Developer-only Activation Codes Management

هذا الملف منفصل عن التطبيق الرئيسي ويستخدم من قبل المطور لإدارة أكواد التفعيل
"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env')

# Database connection
MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.environ.get('DB_NAME', 'test_database')

class ActivationCodeManager:
    def __init__(self):
        self.client = AsyncIOMotorClient(MONGO_URL)
        self.db = self.client[DB_NAME]
    
    async def generate_codes(self, start_number: int, count: int):
        """
        إنشاء أكواد تفعيل جديدة
        Generate new activation codes
        
        Args:
            start_number: الرقم البدئي (مثال: 1 لبدء من 0500001)
            count: عدد الأكواد المراد إنشاؤها
        """
        codes_created = []
        
        for i in range(count):
            code_number = start_number + i
            if code_number > 99999:
                print(f"تم الوصول للحد الأقصى من الأكواد: 99999")
                break
            
            code = f"05{code_number:05d}"
            
            # تحقق من عدم وجود الكود مسبقاً
            existing = await self.db.activation_codes.find_one({"code": code})
            if existing:
                print(f"الكود {code} موجود مسبقاً")
                continue
            
            # إنشاء كود جديد
            activation_code = {
                "code": code,
                "driver_phone": None,
                "is_used": False,
                "expires_at": datetime.utcnow() + timedelta(days=30),
                "created_at": datetime.utcnow()
            }
            
            await self.db.activation_codes.insert_one(activation_code)
            codes_created.append(code)
        
        return codes_created
    
    async def list_codes(self, limit: int = 50, show_used: bool = False):
        """
        عرض قائمة أكواد التفعيل
        List activation codes
        """
        query = {} if show_used else {"is_used": False}
        
        codes = await self.db.activation_codes.find(query).limit(limit).to_list(limit)
        
        print(f"\n{'='*50}")
        print(f"أكواد التفعيل {'(جميع الأكواد)' if show_used else '(المتاحة فقط)'}")
        print(f"{'='*50}")
        
        for code_data in codes:
            status = "مستخدم" if code_data["is_used"] else "متاح"
            expires = code_data["expires_at"].strftime("%Y-%m-%d")
            driver_info = f" - السائق: {code_data['driver_phone']}" if code_data.get('driver_phone') else ""
            
            print(f"الكود: {code_data['code']} | الحالة: {status} | انتهاء الصلاحية: {expires}{driver_info}")
        
        return codes
    
    async def delete_code(self, code: str):
        """
        حذف كود تفعيل
        Delete activation code
        """
        result = await self.db.activation_codes.delete_one({"code": code})
        
        if result.deleted_count > 0:
            print(f"تم حذف الكود: {code}")
            return True
        else:
            print(f"لم يتم العثور على الكود: {code}")
            return False
    
    async def check_code_usage(self):
        """
        إحصائيات استخدام الأكواد
        Code usage statistics
        """
        total_codes = await self.db.activation_codes.count_documents({})
        used_codes = await self.db.activation_codes.count_documents({"is_used": True})
        available_codes = total_codes - used_codes
        expired_codes = await self.db.activation_codes.count_documents({
            "expires_at": {"$lt": datetime.utcnow()}
        })
        
        print(f"\n{'='*40}")
        print(f"إحصائيات أكواد التفعيل")
        print(f"{'='*40}")
        print(f"إجمالي الأكواد: {total_codes}")
        print(f"الأكواد المستخدمة: {used_codes}")
        print(f"الأكواد المتاحة: {available_codes}")
        print(f"الأكواد المنتهية الصلاحية: {expired_codes}")
        
        return {
            "total": total_codes,
            "used": used_codes,
            "available": available_codes,
            "expired": expired_codes
        }
    
    async def close(self):
        """إغلاق الاتصال بقاعدة البيانات"""
        self.client.close()

async def main():
    """واجهة سطر الأوامر لإدارة أكواد التفعيل"""
    manager = ActivationCodeManager()
    
    while True:
        print(f"\n{'='*50}")
        print("إدارة أكواد التفعيل - مطور التطبيق")
        print(f"{'='*50}")
        print("1. إنشاء أكواد جديدة")
        print("2. عرض الأكواد المتاحة")
        print("3. عرض جميع الأكواد")
        print("4. إحصائيات الأكواد")
        print("5. حذف كود")
        print("0. خروج")
        
        choice = input("\nاختر العملية: ")
        
        try:
            if choice == "1":
                start = int(input("الرقم البدئي (مثال: 1): "))
                count = int(input("عدد الأكواد: "))
                
                codes = await manager.generate_codes(start, count)
                print(f"\nتم إنشاء {len(codes)} كود:")
                for code in codes:
                    print(f"  - {code}")
            
            elif choice == "2":
                limit = int(input("عدد الأكواد للعرض (افتراضي 50): ") or 50)
                await manager.list_codes(limit, False)
            
            elif choice == "3":
                limit = int(input("عدد الأكواد للعرض (افتراضي 50): ") or 50)
                await manager.list_codes(limit, True)
            
            elif choice == "4":
                await manager.check_code_usage()
            
            elif choice == "5":
                code = input("أدخل الكود للحذف: ")
                await manager.delete_code(code)
            
            elif choice == "0":
                break
            
            else:
                print("خيار غير صحيح")
        
        except ValueError as e:
            print(f"خطأ في الإدخال: {e}")
        except Exception as e:
            print(f"خطأ: {e}")
    
    await manager.close()
    print("تم إنهاء البرنامج")

if __name__ == "__main__":
    print("أداة إدارة أكواد التفعيل - تطبيق التاكسي الذكي")
    print("هذه الأداة مخصصة للمطور فقط")
    asyncio.run(main())